import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import '../models/multiplayer_models.dart';
import '../providers/multiplayer_provider.dart';
import '../providers/auth_provider.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';
import 'session_chat_screen.dart';

/// Лобби сессии: список игроков, готовность, старт игры
class SessionLobbyScreen extends ConsumerStatefulWidget {
  final SessionData session;
  const SessionLobbyScreen({super.key, required this.session});

  @override
  ConsumerState<SessionLobbyScreen> createState() => _SessionLobbyScreenState();
}

class _SessionLobbyScreenState extends ConsumerState<SessionLobbyScreen> {
  Timer? _refreshTimer;
  late SessionData _session;

  @override
  void initState() {
    super.initState();
    _session = widget.session;
    // Автообновление каждые 3 сек пока в лобби
    _startPolling();
  }

  void _startPolling() {
    _refreshTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (!mounted) return;
      ref.read(multiplayerProvider.notifier).refreshSession(_session.id).then((_) {
        if (mounted) {
          final s = ref.read(multiplayerProvider).currentSession;
          if (s != null) {
            setState(() => _session = s);
            // Если игра началась — переходим в чат
            if (s.isPlaying) {
              _refreshTimer?.cancel();
              _enterGame(s);
            }
          }
        }
      });
    });
  }

  void _enterGame(SessionData s) {
    final auth = ref.read(authProvider);
    ref.read(multiplayerProvider.notifier).setUserId(auth.userId ?? '');
    ref.read(multiplayerProvider.notifier).loadMessages(s.id);
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => SessionChatScreen(sessionId: s.id)),
    );
  }

  void _toggleReady() async {
    final auth = ref.read(authProvider);
    final myMember = _session.members.where((m) => m.userId == auth.userId).isEmpty
        ? null
        : _session.members.firstWhere((m) => m.userId == auth.userId);
    if (myMember == null) return;

    // Если уже ready — не даём снять (или даём, упростим)
    if (myMember.isReady) return;

    // Нужен выбор персонажа
    final chars = await ref.read(chatApiServiceProvider).listCharacters();
    if (!mounted) return;
    if (chars.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Сначала создайте персонажа во вкладке "Соло"'), backgroundColor: Colors.orange),
      );
      return;
    }

    // Диалог выбора персонажа
    final charId = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Выберите персонажа', style: TextStyle(color: AppTheme.gold)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.builder(
            shrinkWrap: true,
            itemCount: chars.length,
            itemBuilder: (_, i) {
              final c = chars[i];
              return ListTile(
                title: Text('${c.name} — ${c.race} ${c.className} (ур. ${c.level})',
                  style: const TextStyle(color: AppTheme.parchment)),
                onTap: () => Navigator.pop(ctx, c.id),
              );
            },
          ),
        ),
      ),
    );
    if (charId != null) {
      await ref.read(multiplayerProvider.notifier).setReady(_session.id, charId);
    }
  }

  void _startGame() async {
    final result = await ref.read(multiplayerProvider.notifier).startSession(_session.id);
    if (!result && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ref.read(multiplayerProvider).error ?? 'Не все готовы'),
          backgroundColor: Colors.orange,
        ),
      );
    }
  }

  void _rollInitiative() async {
    await ref.read(multiplayerProvider.notifier).rollInitiative(_session.id);
  }

  void _deleteSession() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Удалить партию?', style: TextStyle(color: AppTheme.gold)),
        content: Text('Вы уверены, что хотите удалить «${_session.name}»?\nВсе игроки будут отключены.', style: const TextStyle(color: AppTheme.parchment)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Удалить', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirm == true && mounted) {
      final ok = await ref.read(multiplayerProvider.notifier).deleteSession(_session.id);
      if (mounted) {
        if (ok) Navigator.pop(context); // back to sessions list
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ok ? 'Партия удалена' : 'Ошибка удаления'),
            backgroundColor: ok ? Colors.green : Colors.red,
          ),
        );
      }
    }
  }

  void _copyInvite() {
    Clipboard.setData(ClipboardData(text: _session.inviteCode));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Код скопирован!'), backgroundColor: Colors.green),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.read(authProvider);
    final isOwner = _session.isOwner(auth.userId ?? '');
    final allReady = _session.members.length >= 2 &&
        _session.members.every((m) => m.isReady);
    final myMember = _session.members.where((m) => m.userId == auth.userId).isEmpty
        ? null
        : _session.members.firstWhere((m) => m.userId == auth.userId);

    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: Text(_session.name),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.copy),
            tooltip: 'Копировать код приглашения',
            onPressed: _copyInvite,
          ),
        ],
      ),
      body: Column(
        children: [
          // Код приглашения
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3)),
            ),
            child: Row(children: [
              const Icon(Icons.vpn_key, color: AppTheme.gold),
              const SizedBox(width: 12),
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Код приглашения', style: TextStyle(color: AppTheme.gold, fontSize: 13)),
                Text(_session.inviteCode,
                  style: const TextStyle(color: AppTheme.parchment, fontSize: 24, fontWeight: FontWeight.bold, letterSpacing: 4)),
              ]),
              const Spacer(),
              TextButton.icon(
                onPressed: _copyInvite,
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Копировать'),
                style: TextButton.styleFrom(foregroundColor: AppTheme.gold),
              ),
            ]),
          ),

          // Заголовок игроков
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [
              Text('Игроки (${_session.members.length})',
                style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 16)),
              const Spacer(),
              _statusBadge(_session.state),
            ]),
          ),

          // Список игроков
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _session.members.length,
              itemBuilder: (_, i) {
                final m = _session.members[i];
                final isMe = m.userId == auth.userId;
                return Card(
                  color: AppTheme.darkBrown,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: m.isReady ? Colors.green.withValues(alpha: 0.5) : AppTheme.gold.withValues(alpha: 0.2),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(children: [
                      // Аватар
                      CircleAvatar(
                        backgroundColor: m.isReady ? Colors.green : AppTheme.gold.withValues(alpha: 0.3),
                        radius: 18,
                        child: Icon(
                          m.isReady ? Icons.check : Icons.person,
                          color: m.isReady ? Colors.white : AppTheme.parchment,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            Text(m.username, style: const TextStyle(color: AppTheme.parchment, fontWeight: FontWeight.bold)),
                            if (isMe) const Text(' (вы)', style: TextStyle(color: AppTheme.gold, fontSize: 12)),
                            if (m.userId == _session.ownerId) ...[
                              const SizedBox(width: 6),
                              const Text('👑', style: TextStyle(fontSize: 14)),
                            ],
                          ]),
                          if (m.characterName != null)
                            Text(m.characterName!,
                              style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.7), fontSize: 13)),
                          if (m.initiative != null)
                            Text('Инициатива: ${m.initiative}',
                              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12)),
                        ]),
                      ),
                      if (m.isReady)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text('Готов', style: TextStyle(color: Colors.green, fontSize: 12)),
                        ),
                    ]),
                  ),
                );
              },
            ),
          ),

          // Кнопки действий
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(children: [
                if (!(myMember?.isReady ?? false))
                  ElevatedButton.icon(
                    onPressed: _toggleReady,
                    icon: const Icon(Icons.check),
                    label: const Text('Я готов'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.gold, foregroundColor: Colors.black,
                      minimumSize: const Size(double.infinity, 48),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                if (isOwner && _session.isLobby) ...[
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _rollInitiative,
                        icon: const Icon(Icons.casino, size: 16),
                        label: const Text('Инициатива'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.gold,
                          side: const BorderSide(color: AppTheme.gold),
                          minimumSize: const Size(0, 40),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      flex: 2,
                      child: ElevatedButton.icon(
                        onPressed: allReady ? _startGame : null,
                        icon: const Icon(Icons.play_arrow),
                        label: Text(allReady ? 'Начать игру!' : 'Ждём готовности...'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: allReady ? Colors.green : Colors.grey,
                          foregroundColor: Colors.white,
                          minimumSize: const Size(0, 48),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),
                  ]),
                ],
                if (isOwner && _session.isLobby) ...[
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: _deleteSession,
                    icon: const Icon(Icons.delete_outline, size: 18),
                    label: const Text('Удалить партию'),
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.redAccent.withValues(alpha: 0.7),
                    ),
                  ),
                ],
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _statusBadge(String state) {
    final (icon, label, color) = switch (state) {
      'playing' => (Icons.play_arrow, 'В игре', Colors.green),
      _ => (Icons.lock_clock, 'Лобби', Colors.orange),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color, fontSize: 12)),
      ]),
    );
  }
}
