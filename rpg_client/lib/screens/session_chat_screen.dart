import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/multiplayer_models.dart';
import '../providers/multiplayer_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/api_service_provider.dart';
import '../services/ws_service.dart';
import '../theme/app_theme.dart';

/// Групповой чат игровой сессии (WebSocket + REST fallback)
class SessionChatScreen extends ConsumerStatefulWidget {
  final String sessionId;
  const SessionChatScreen({super.key, required this.sessionId});

  @override
  ConsumerState<SessionChatScreen> createState() => _SessionChatScreenState();
}

class _SessionChatScreenState extends ConsumerState<SessionChatScreen> {
  final _scrollCtrl = ScrollController();
  final _msgCtrl = TextEditingController();
  bool _initialized = false;
  bool _showScrollButton = false;

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _init());
  }

  void _onScroll() {
    if (!mounted) return;
    try {
      if (!_scrollCtrl.hasClients) return;
      final isAway = _scrollCtrl.position.pixels < _scrollCtrl.position.maxScrollExtent - 100;
      if (_showScrollButton != isAway) {
        setState(() => _showScrollButton = isAway);
      }
    } catch (_) {}
  }

  void _init() {
    if (_initialized) return;
    _initialized = true;
    _initAsync();
  }

  Future<void> _initAsync() async {

    final api = ref.read(chatApiServiceProvider);
    final auth = ref.read(authProvider);
    final mp = ref.read(multiplayerProvider.notifier);

    mp.setUserId(auth.userId ?? '');

    // Подключаем WebSocket и ждём
    await mp.connectWs(widget.sessionId, api.token ?? '');

    // Слушаем новые сообщения для скролла
    ref.listen(multiplayerProvider.select((s) => s.messages.length), (_, __) {
      _scrollToBottom();
    });

    // Загружаем историю сообщений
    await mp.loadMessages(widget.sessionId);

    // Слушаем turnError для показа SnackBar
    ref.listen(multiplayerProvider.select((s) => s.turnError), (_, turnError) {
      if (turnError != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(children: [
              const Icon(Icons.block, color: Colors.orange, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text(turnError, style: const TextStyle(color: Colors.white))),
            ]),
            backgroundColor: Colors.red.shade900,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 5),
            action: SnackBarAction(
              label: 'ЗАКРЫТЬ',
              textColor: Colors.white,
              onPressed: () {
                ScaffoldMessenger.of(context).hideCurrentSnackBar();
              },
            ),
          ),
        );
        ref.read(multiplayerProvider.notifier).clearTurnError();
      }
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _send() {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty) return;
    _msgCtrl.clear();
    ref.read(multiplayerProvider.notifier).sendChat(text);
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    _msgCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(multiplayerProvider);
    final auth = ref.read(authProvider);
    final currentUserId = auth.userId ?? '';

    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            ref.read(multiplayerProvider.notifier).disconnectWs();
            Navigator.pop(context);
          },
        ),
        title: Row(children: [
          const Text('Групповой чат', style: TextStyle(fontSize: 16)),
          const SizedBox(width: 8),
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: state.wsConnected ? Colors.green : Colors.red,
            ),
          ),
        ]),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить сообщения',
            onPressed: () => ref.read(multiplayerProvider.notifier).loadMessages(widget.sessionId),
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: state.messages.isEmpty && !state.aiTyping
            ? _buildEmpty()
            : Stack(children: [
                RepaintBoundary(
                    child: ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
                    addAutomaticKeepAlives: true,
                    addRepaintBoundaries: true,
                    itemCount: state.messages.length + (state.aiTyping ? 1 : 0),
                    itemBuilder: (ctx, i) {
                      if (i == state.messages.length) {
                        return Padding(
                          padding: const EdgeInsets.all(12),
                          child: Row(children: [
                            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.gold)),
                            const SizedBox(width: 12),
                            Text('Мастер пишет...', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35), fontStyle: FontStyle.italic)),
                          ]),
                        );
                      }
                      final msg = state.messages[i];
                      final isMe = msg.userId == currentUserId;
                      final isDm = msg.userId == 'dm';
                      return _msgBubble(msg, isMe: isMe, isDm: isDm);
                    },
                  ),
                ),
                if (_showScrollButton)
                  Positioned(
                    bottom: 8,
                    right: 12,
                    child: FloatingActionButton.small(
                      heroTag: 'scroll_to_bottom_session',
                      backgroundColor: AppTheme.gold.withValues(alpha: 0.85),
                      onPressed: () {
                        _scrollCtrl.animateTo(
                          _scrollCtrl.position.maxScrollExtent,
                          duration: const Duration(milliseconds: 200),
                          curve: Curves.easeOut,
                        );
                      },
                      child: const Icon(Icons.keyboard_arrow_down, color: Colors.black87, size: 28),
                    ),
                  ),
              ]),
        ),
        _buildInput(),
      ]),
    );
  }

  Widget _msgBubble(GameMessage msg, {required bool isMe, required bool isDm}) {
    final alignment = isDm ? Alignment.centerLeft : (isMe ? Alignment.centerRight : Alignment.centerLeft);
    final bgColor = isDm
        ? AppTheme.gold.withValues(alpha: 0.1)
        : isMe
          ? AppTheme.gold.withValues(alpha: 0.2)
          : AppTheme.darkBrown;
    final borderColor = isDm ? AppTheme.gold.withValues(alpha: 0.3) : AppTheme.gold.withValues(alpha: 0.1);

    return Align(
      alignment: alignment,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8, left: 8, right: 8),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (isDm)
            const Text('🎭 Мастер', style: TextStyle(color: AppTheme.gold, fontSize: 12, fontWeight: FontWeight.bold))
          else
            Text(isMe ? 'Вы' : (msg.userId.substring(0, 8)),
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11)),
          const SizedBox(height: 4),
          Text(msg.content, style: const TextStyle(color: AppTheme.parchment, fontSize: 15)),
          if (msg.diceRoll != null && msg.diceRoll!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '🎲 ${msg.diceRoll}',
                  style: const TextStyle(color: Colors.redAccent, fontSize: 12),
                ),
              ),
            ),
        ]),
      ),
    );
  }

  Widget _buildEmpty() => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.chat, size: 64, color: AppTheme.gold.withValues(alpha: 0.3)),
      const SizedBox(height: 16),
      Text('Чат пуст', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 16)),
      const SizedBox(height: 8),
      Text('Напишите что-нибудь, чтобы начать приключение!',
        style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35), fontSize: 13)),
    ]),
  );

  Widget _buildInput() {
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppTheme.darkBrown,
          border: Border(top: BorderSide(color: AppTheme.gold.withValues(alpha: 0.1))),
        ),
        child: Row(children: [
          Expanded(
            child: TextField(
              controller: _msgCtrl,
              style: const TextStyle(color: AppTheme.parchment),
              decoration: InputDecoration(
                hintText: 'Ваше действие...',
                hintStyle: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3)),
                filled: true,
                fillColor: AppTheme.gold.withValues(alpha: 0.05),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              ),
              onSubmitted: (_) => _send(),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _send,
            child: Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                color: AppTheme.gold,
                borderRadius: BorderRadius.circular(22),
              ),
              child: const Icon(Icons.send, color: Colors.black, size: 20),
            ),
          ),
        ]),
      ),
    );
  }
}
