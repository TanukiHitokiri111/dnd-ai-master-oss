import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/multiplayer_models.dart';
import '../providers/multiplayer_provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import 'session_lobby_screen.dart';

/// Экран со списком сессий + создание/присоединение
class SessionsScreen extends ConsumerStatefulWidget {
  const SessionsScreen({super.key});

  @override
  ConsumerState<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends ConsumerState<SessionsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(multiplayerProvider.notifier).loadSessions();
    });
  }

  void _createSession() async {
    final nameCtrl = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Новая партия', style: TextStyle(color: AppTheme.gold)),
        content: TextField(
          controller: nameCtrl,
          style: const TextStyle(color: AppTheme.parchment),
          decoration: InputDecoration(
            hintText: 'Название приключения',
            hintStyle: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35)),
            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: AppTheme.gold)),
          ),
          autofocus: true,
          onSubmitted: (_) => Navigator.pop(ctx, nameCtrl.text),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, nameCtrl.text),
            child: const Text('Создать', style: TextStyle(color: AppTheme.gold)),
          ),
        ],
      ),
    );
    if (name != null && name.trim().isNotEmpty) {
      final s = await ref.read(multiplayerProvider.notifier).createSession(name.trim());
      if (s != null && mounted) {
        Navigator.push(context, MaterialPageRoute(builder: (_) => SessionLobbyScreen(session: s)));
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ref.read(multiplayerProvider).error ?? 'Ошибка создания партии'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _joinSession() async {
    final codeCtrl = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Присоединиться', style: TextStyle(color: AppTheme.gold)),
        content: TextField(
          controller: codeCtrl,
          style: const TextStyle(color: AppTheme.parchment),
          decoration: InputDecoration(
            hintText: 'Код приглашения (напр. AB12CD)',
            hintStyle: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35)),
            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: AppTheme.gold)),
          ),
          textCapitalization: TextCapitalization.characters,
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, codeCtrl.text),
            child: const Text('Войти', style: TextStyle(color: AppTheme.gold)),
          ),
        ],
      ),
    );
    if (code != null && code.trim().isNotEmpty) {
      final ok = await ref.read(multiplayerProvider.notifier).joinSession(code.trim().toUpperCase());
      if (ok) {
        ref.read(multiplayerProvider.notifier).loadSessions();
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ref.read(multiplayerProvider).error ?? 'Ошибка'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _openSession(SessionData s) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => SessionLobbyScreen(session: s)));
  }

  void _deleteSession(SessionData s) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Удалить партию?', style: TextStyle(color: AppTheme.gold)),
        content: Text('Вы уверены, что хотите удалить «${s.name}»?', style: const TextStyle(color: AppTheme.parchment)),
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
      final ok = await ref.read(multiplayerProvider.notifier).deleteSession(s.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(ok ? 'Партия удалена' : 'Ошибка удаления'),
            backgroundColor: ok ? Colors.green : Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(multiplayerProvider);
    final auth = ref.watch(authProvider);

    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: const Text('Партии'),
        actions: [
          if (auth.isLoggedIn)
            TextButton(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              child: Text(auth.username ?? '', style: const TextStyle(color: AppTheme.gold)),
            )
          else
            TextButton(
              onPressed: () => Navigator.pushReplacementNamed(context, '/login'),
              child: const Text('Войти', style: TextStyle(color: AppTheme.gold)),
            ),
        ],
      ),
      body: state.isLoading
        ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
        : state.sessions.isEmpty
          ? _buildEmpty()
          : RefreshIndicator(
              onRefresh: () => ref.read(multiplayerProvider.notifier).loadSessions(),
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: state.sessions.length + 1, // +1 for buttons
                itemBuilder: (ctx, i) {
                  if (i == state.sessions.length) return _buildButtons();
                  final s = state.sessions[i];
                  return Card(
                    color: AppTheme.darkBrown,
                    margin: const EdgeInsets.only(bottom: 8),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2)),
                    ),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => _openSession(s),
                      onLongPress: s.isOwner(auth.userId ?? '')
                        ? () => _deleteSession(s)
                        : null,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Row(
                          children: [
                            Container(
                              width: 44, height: 44,
                              decoration: BoxDecoration(
                                color: s.isPlaying ? Colors.green.withValues(alpha: 0.2) : AppTheme.gold.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(
                                s.isPlaying ? Icons.play_arrow : Icons.groups,
                                color: s.isPlaying ? Colors.green : AppTheme.gold,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(s.name, style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15)),
                                  const SizedBox(height: 4),
                                  Row(
                                    children: [
                                      _badge(s.isPlaying ? '🎮 Игра' : '🏠 Лобби', s.isPlaying ? Colors.green : Colors.orange),
                                      const SizedBox(width: 8),
                                      _badge('${s.members.length} игроков', null),
                                      const SizedBox(width: 8),
                                      if (s.isOwner(auth.userId ?? ''))
                                        _badge('👑 Хост', AppTheme.gold),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.chevron_right, color: AppTheme.gold),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }

  Widget _badge(String text, Color? color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: (color ?? AppTheme.parchment).withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(text, style: TextStyle(color: color ?? AppTheme.parchment, fontSize: 11)),
    );
  }

  Widget _buildEmpty() => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.groups, size: 64, color: AppTheme.gold.withValues(alpha: 0.4)),
      const SizedBox(height: 16),
      Text('Нет активных партий', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 18)),
      const SizedBox(height: 8),
      Text('Создайте свою или присоединитесь по коду', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 13)),
      const SizedBox(height: 24),
      _buildButtons(),
    ]),
  );

  Widget _buildButtons() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 8),
    child: Column(children: [
      ElevatedButton.icon(
        onPressed: _createSession,
        icon: const Icon(Icons.add),
        label: const Text('Создать партию'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppTheme.gold, foregroundColor: Colors.black,
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
      const SizedBox(height: 12),
      OutlinedButton.icon(
        onPressed: _joinSession,
        icon: const Icon(Icons.login, size: 18),
        label: const Text('Присоединиться по коду'),
        style: OutlinedButton.styleFrom(
          foregroundColor: AppTheme.gold.withValues(alpha: 0.6),
          side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3)),
          minimumSize: const Size(double.infinity, 40),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
    ]),
  );
}
