import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../config/app_config.dart';
import '../models/chat_message.dart';
import '../services/roll_request_parser.dart';
import '../theme/app_theme.dart';

/// Создаётся ОДИН раз, не на каждое сообщение.
final _assistantMarkdownStyle = MarkdownStyleSheet(
  p: TextStyle(color: AppTheme.parchment, fontSize: 15, height: 1.4),
  strong: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold),
  listBullet: TextStyle(color: AppTheme.gold),
  h1: TextStyle(color: AppTheme.gold, fontSize: 20),
  h2: TextStyle(color: AppTheme.gold, fontSize: 18),
  h3: TextStyle(color: AppTheme.gold, fontSize: 16),
  blockquote: TextStyle(color: AppTheme.parchment, fontStyle: FontStyle.italic),
  code: TextStyle(
    color: AppTheme.gold,
    backgroundColor: Color(0x66000000),
  ),
);

final _systemMarkdownStyle = MarkdownStyleSheet(
  p: TextStyle(color: AppTheme.gold, fontSize: 14),
  strong: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold),
);

class ChatMessageTile extends StatelessWidget {
  final ChatMessage message;
  final void Function(RollRequest req)? onRollRequest;

  const ChatMessageTile({super.key, required this.message, this.onRollRequest});

  @override
  Widget build(BuildContext context) {
    final maxWidth = MediaQuery.of(context).size.width * 0.85;

    switch (message.role) {
      case 'user':
        return RepaintBoundary(
          child: Align(
            alignment: Alignment.centerRight,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.leather.withValues(alpha: 0.35),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.gold.withValues(alpha: 0.6)),
                ),
                child: Text(
                  message.content,
                  style: const TextStyle(color: AppTheme.parchment, fontSize: 15),
                ),
              ),
            ),
          ),
        );

      case 'assistant':
        final rollReq = parseRollRequest(message.content);
        return RepaintBoundary(
          child: Align(
            alignment: Alignment.centerLeft,
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.darkBrown.withValues(alpha: 0.9),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.leather.withValues(alpha: 0.5)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    MarkdownBody(
                      data: message.content,
                      selectable: true,
                      styleSheet: _assistantMarkdownStyle,
                    ),
                    if (message.streaming) const _StreamingCursor(),
                    if (message.imageUrl != null && message.imageUrl!.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: Image.network(
                          AppConfig.baseUrl + message.imageUrl!,
                          width: double.infinity,
                          fit: BoxFit.cover,
                          loadingBuilder: (context, child, progress) {
                            if (progress == null) return child;
                            return Container(
                              height: 180,
                              alignment: Alignment.center,
                              color: Colors.black.withValues(alpha: 0.2),
                              child: const CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppTheme.gold,
                              ),
                            );
                          },
                          errorBuilder: (context, error, stack) => Container(
                            height: 100,
                            alignment: Alignment.center,
                            color: Colors.black.withValues(alpha: 0.2),
                            child: const Text('🖼️ (картинка не загрузилась)',
                                style: TextStyle(color: Colors.white70, fontSize: 12)),
                          ),
                        ),
                      ),
                    ],
                    if (message.appearanceUrl != null && message.appearanceUrl!.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppTheme.gold.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.gold.withValues(alpha: 0.4)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Row(
                              children: [
                                Text('🪞 ', style: TextStyle(fontSize: 14)),
                                Text('Ваше отражение',
                                    style: TextStyle(
                                        color: AppTheme.gold, fontSize: 12, fontWeight: FontWeight.bold)),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: Image.network(
                                AppConfig.baseUrl + message.appearanceUrl!,
                                width: double.infinity,
                                fit: BoxFit.cover,
                                loadingBuilder: (context, child, progress) {
                                  if (progress == null) return child;
                                  return Container(
                                    height: 160,
                                    alignment: Alignment.center,
                                    color: Colors.black.withValues(alpha: 0.2),
                                    child: const CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: AppTheme.gold,
                                    ),
                                  );
                                },
                                errorBuilder: (context, error, stack) => Container(
                                  height: 100,
                                  alignment: Alignment.center,
                                  color: Colors.black.withValues(alpha: 0.2),
                                  child: const Text('🖼️ (отражение не загрузилось)',
                                      style: TextStyle(color: Colors.white70, fontSize: 12)),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (message.npcUrl != null && message.npcUrl!.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppTheme.gold.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.gold.withValues(alpha: 0.4)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Row(
                              children: [
                                const Text('👤 ', style: TextStyle(fontSize: 14)),
                                Expanded(
                                  child: Text(
                                    message.npcName != null && message.npcName!.isNotEmpty
                                        ? 'Вы видите: ${message.npcName}'
                                        : 'Вы видите',
                                    style: const TextStyle(
                                        color: AppTheme.gold, fontSize: 12, fontWeight: FontWeight.bold),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: Image.network(
                                AppConfig.baseUrl + message.npcUrl!,
                                width: double.infinity,
                                fit: BoxFit.cover,
                                loadingBuilder: (context, child, progress) {
                                  if (progress == null) return child;
                                  return Container(
                                    height: 160,
                                    alignment: Alignment.center,
                                    color: Colors.black.withValues(alpha: 0.2),
                                    child: const CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: AppTheme.gold,
                                    ),
                                  );
                                },
                                errorBuilder: (context, error, stack) => Container(
                                  height: 100,
                                  alignment: Alignment.center,
                                  color: Colors.black.withValues(alpha: 0.2),
                                  child: const Text('🖼️ (изображение не загрузилось)',
                                      style: TextStyle(color: Colors.white70, fontSize: 12)),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    if (rollReq != null && onRollRequest != null) ...[
                      const SizedBox(height: 10),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () => onRollRequest!(rollReq),
                          icon: Text(
                            rollReq.isMultiDice ? '🎲×${rollReq.count}' : '🎲',
                            style: const TextStyle(fontSize: 18),
                          ),
                          label: Text(
                            rollReq.isMultiDice
                                ? 'Бросить ${rollReq.count}d${rollReq.diceType}${_fmtMod(rollReq.modifier)}${rollReq.label.isNotEmpty ? ' — ${rollReq.label}' : ''}'
                                : rollReq.label.isNotEmpty
                                    ? 'Бросить d${rollReq.diceType}${_fmtMod(rollReq.modifier)} — ${rollReq.label}'
                                    : 'Бросить d${rollReq.diceType}${_fmtMod(rollReq.modifier)}',
                            style: const TextStyle(fontSize: 13),
                          ),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppTheme.gold,
                            side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.5)),
                            backgroundColor: AppTheme.gold.withValues(alpha: 0.08),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        );

      default:
        return RepaintBoundary(
          child: Center(
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 24),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.35),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3)),
              ),
              child: MarkdownBody(
                data: message.content,
                styleSheet: _systemMarkdownStyle,
              ),
            ),
          ),
        );
    }
  }

  String _fmtMod(int mod) => mod >= 0 ? ' +$mod' : ' $mod';
}

/// Мигающий курсор при стриминге ответа.
class _StreamingCursor extends StatefulWidget {
  const _StreamingCursor();

  @override
  State<_StreamingCursor> createState() => _StreamingCursorState();
}

class _StreamingCursorState extends State<_StreamingCursor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 600))
        ..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _controller,
      child: const Padding(
        padding: EdgeInsets.only(top: 4),
        child: Text('▍', style: TextStyle(color: AppTheme.gold, fontSize: 15)),
      ),
    );
  }
}
