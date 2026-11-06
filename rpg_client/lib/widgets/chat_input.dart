import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import '../theme/app_theme.dart';

class ChatInput extends ConsumerStatefulWidget {
  const ChatInput({super.key});

  @override
  ConsumerState<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends ConsumerState<ChatInput> {
  final TextEditingController _controller = TextEditingController();
  DateTime _lastSendTime = DateTime(2000);
  static const _minSendInterval = Duration(milliseconds: 500);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _send() {
    final now = DateTime.now();
    if (now.difference(_lastSendTime) < _minSendInterval) return;
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _lastSendTime = now;
    ref.read(chatProvider.notifier).sendMessageStream(text);
    _controller.clear();
  }

  void _quickSend(String text) {
    final now = DateTime.now();
    if (now.difference(_lastSendTime) < _minSendInterval) return;
    _lastSendTime = now;
    ref.read(chatProvider.notifier).sendMessageStream(text);
  }

  void _openMap() {
    final character = ref.read(chatProvider).character;
    if (character == null) return;
    Navigator.of(context).pushNamed('/map', arguments: {
      'characterId': character.id,
      'characterName': character.name,
    });
  }

  @override
  Widget build(BuildContext context) {
    final isLoading = ref.watch(chatProvider.select((s) => s.isLoading));

    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        color: AppTheme.darkBrown.withValues(alpha: 0.6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Быстрые действия
            if (!isLoading)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    _quickChip('😴 Короткий отдых', 'Я делаю короткий отдых'),
                    const SizedBox(width: 6),
                    _quickChip('🏕️ Длинный отдых', 'Я делаю длинный отдых'),
                    const Spacer(),
                    IconButton(
                      onPressed: _openMap,
                      tooltip: 'Карта мира',
                      visualDensity: VisualDensity.compact,
                      icon: const Icon(Icons.map, color: AppTheme.gold, size: 22),
                    ),
                  ],
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    enabled: !isLoading,
                    minLines: 1,
                    maxLines: 5,
                    textInputAction: TextInputAction.send,
                    textCapitalization: TextCapitalization.sentences,
                    style: const TextStyle(color: AppTheme.parchment),
                    decoration: InputDecoration(
                      hintText: isLoading
                          ? 'Мастер отвечает...'
                          : 'Опишите ваше действие...',
                      hintStyle:
                          TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4)),
                      filled: true,
                      fillColor: Colors.black.withValues(alpha: 0.3),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: isLoading ? null : _send,
                  tooltip: 'Отправить',
                  icon: isLoading
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: AppTheme.gold),
                        )
                      : const Icon(Icons.send, color: AppTheme.gold),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _quickChip(String label, String message) {
    return InkWell(
      onTap: () => _quickSend(message),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: AppTheme.gold.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.gold.withValues(alpha: 0.2)),
        ),
        child: Text(label,
            style: const TextStyle(color: AppTheme.gold, fontSize: 12)),
      ),
    );
  }
}
