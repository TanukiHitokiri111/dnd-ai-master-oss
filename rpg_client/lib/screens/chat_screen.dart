import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import '../providers/api_service_provider.dart';
import '../services/roll_request_parser.dart';
import '../theme/app_theme.dart';
import '../models/chat_message.dart';
import '../widgets/chat_message_tile.dart';
import '../widgets/chat_input.dart';
import '../widgets/dice_roller.dart';
import '../widgets/typing_indicator.dart';
import 'level_up_screen.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _scrollController = ScrollController();
  bool _showScrollButton = false;
  bool _initialLoadDone = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await ref.read(chatProvider.notifier).loadSavedState();
      // После первой загрузки — скроллим вниз с задержкой на лейаут
      if (mounted) {
        _initialLoadDone = true;
        _scrollToBottom();
      }
    });
  }

  void _onScroll() {
    if (!mounted) return;
    try {
      if (!_scrollController.hasClients) return;
      final isAway = _scrollController.position.pixels < _scrollController.position.maxScrollExtent - 100;
      if (_showScrollButton != isAway) {
        setState(() => _showScrollButton = isAway);
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  bool _isStreaming(List<ChatMessage> messages) =>
      messages.isNotEmpty && messages.last.streaming;

  void _scrollToBottom({int retries = 3}) {
    if (!mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (_scrollController.hasClients && _scrollController.position.maxScrollExtent > 0) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      } else if (retries > 0 && mounted) {
        // Лейаут ещё не завершён — пробуем следующий кадр
        _scrollToBottom(retries: retries - 1);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    ref.listen(chatProvider.select((s) => s.messages.length), (prev, next) {
      if (prev != next) _scrollToBottom();
    });

    // Автопрокрутка при стриминге: контент последнего сообщения растёт по чанкам
    ref.listen(
      chatProvider.select((s) => s.messages.isEmpty ? null : s.messages.last.content),
      (prev, next) {
        if (prev != next && next != null && next.isNotEmpty) _scrollToBottom();
      },
    );

    // Левелап: сервер прислал leveled_up — открываем экран повышения уровня
    ref.listen(chatProvider.select((s) => s.leveledUp), (prev, next) {
      if (next == true) {
        final char = ref.read(chatProvider).character;
        if (char != null) {
          // Сбрасываем флаг, чтобы не открывать повторно
          ref.read(chatProvider.notifier).consumeLevelUp();
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => LevelUpScreen(
                  characterId: char.id,
                  characterName: char.name,
                  currentLevel: char.level,
                  currentClass: char.className,
                  stats: char.stats,
                ),
              ),
            ).then((_) {
              // После закрытия экрана левелапа — перечитываем персонажа (HP, статы, уровень)
              ref.read(chatProvider.notifier).reloadCharacter();
            });
          });
        }
      }
    });

    final character = chatState.character;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('D&D AI Master', style: TextStyle(fontSize: 16)),
            if (character != null)
              Text(
                '${character.name} — ${character.race} ${character.className} lvl ${character.level}  |  HP: ${character.hpCurrent}/${character.hpMax}',
                style: TextStyle(fontSize: 11, color: AppTheme.gold.withValues(alpha: 0.6)),
              ),
          ],
        ),
        centerTitle: false,
        titleSpacing: 0,
        actions: [
          if (character != null)
            IconButton(
              icon: const Icon(Icons.bar_chart_rounded),
              tooltip: 'Статус',
              onPressed: () => Navigator.pushNamed(context, '/status', arguments: {
                'characterId': character.id,
                'characterName': character.name,
              }),
            ),
          const DiceRoller(),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Очистить чат',
            onPressed: () => _showClearDialog(context),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          if (character != null && character.isDead)
            MaterialBanner(
              backgroundColor: Colors.red.shade900,
              content: const Text(
                '💀 Твой персонаж погиб. История завершена.',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              actions: [
                TextButton.icon(
                  onPressed: () => _startNewGame(context),
                  icon: const Icon(Icons.add, color: Colors.white, size: 18),
                  label: const Text('НОВАЯ ИСТОРИЯ', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  style: TextButton.styleFrom(backgroundColor: Colors.red.shade700),
                ),
              ],
            ),
          if (chatState.errorMessage != null)
            MaterialBanner(
              backgroundColor: AppTheme.bloodRed.withValues(alpha: 0.9),
              content: Text(chatState.errorMessage!, style: const TextStyle(color: Colors.white)),
              actions: [
                TextButton(
                  onPressed: () => ref.read(chatProvider.notifier).clearError(),
                  child: const Text('ЗАКРЫТЬ', style: TextStyle(color: Colors.white)),
                ),
              ],
            ),
          Expanded(
            child: Stack(
              children: [
                chatState.messages.isEmpty && !chatState.isLoading
                    ? _buildEmptyState(context)
                    : RepaintBoundary(
                        child: ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.only(bottom: 16),
                          addAutomaticKeepAlives: true,
                          addRepaintBoundaries: true,
                          itemCount: chatState.messages.length + ((chatState.isLoading && !_isStreaming(chatState.messages)) ? 1 : 0),
                          itemBuilder: (context, index) {
                            if (index == chatState.messages.length) {
                              return const TypingIndicator();
                            }
                            return ChatMessageTile(
                              key: ValueKey('msg_${chatState.messages[index].id}_$index'),
                              message: chatState.messages[index],
                              onRollRequest: (req) {
                                ref.read(chatProvider.notifier).rollDice(
                                  req.diceType,
                                  modifier: req.modifier,
                                  label: req.label,
                                  count: req.count,
                                  advantage: req.advantage,
                                  disadvantage: req.disadvantage,
                                );
                              },
                            );
                          },
                        ),
                      ),
                // Scroll button — всегда в дереве, показывается/скрывается через прозрачность
                Positioned(
                  bottom: 8,
                  right: 12,
                  child: AnimatedOpacity(
                    opacity: _showScrollButton ? 1.0 : 0.0,
                    duration: const Duration(milliseconds: 200),
                    child: FloatingActionButton.small(
                      heroTag: 'scroll_to_bottom',
                      backgroundColor: AppTheme.gold.withValues(alpha: 0.85),
                      onPressed: _showScrollButton ? () {
                        if (_scrollController.hasClients) {
                          _scrollController.animateTo(
                            _scrollController.position.maxScrollExtent,
                            duration: const Duration(milliseconds: 200),
                            curve: Curves.easeOut,
                          );
                        }
                      } : null,
                      child: const Icon(Icons.keyboard_arrow_down, color: Colors.black87, size: 28),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const ChatInput(),
        ],
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.auto_stories, size: 80, color: AppTheme.gold.withValues(alpha: 0.3)),
          const SizedBox(height: 16),
          Text('Начните своё приключение...',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppTheme.parchment.withValues(alpha: 0.5))),
          const SizedBox(height: 8),
          Text('Например: «Я осматриваю таверну»',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.parchment.withValues(alpha: 0.3))),
        ],
      ),
    );
  }

  void _showClearDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Очистить чат?', style: TextStyle(color: AppTheme.gold)),
        content: const Text(
          'История будет удалена на устройстве И на сервере. Это действие нельзя отменить.',
          style: TextStyle(color: AppTheme.parchment),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('ОТМЕНА'),
          ),
          TextButton(
            onPressed: () {
              ref.read(chatProvider.notifier).clearChat();
              Navigator.pop(dialogContext);
            },
            child: const Text('ОЧИСТИТЬ', style: TextStyle(color: AppTheme.bloodRed)),
          ),
        ],
      ),
    );
  }

  void _startNewGame(BuildContext context) async {
    final api = ref.read(chatApiServiceProvider);
    final char = ref.read(chatProvider).character;
    if (char == null) return;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Новая история', style: TextStyle(color: AppTheme.gold)),
        content: Text(
          'Удалить персонажа «${char.name}» и начать заново? История будет безвозвратно удалена.',
          style: const TextStyle(color: AppTheme.parchment),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('ОТМЕНА')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('УДАЛИТЬ И НАЧАТЬ ЗАНОВО', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      await api.deleteCharacter(char.id);
      if (mounted) {
        ref.read(chatProvider.notifier).clearCharacter();
        ref.read(chatProvider.notifier).clearChat();
        Navigator.pop(context);
      }
    }
  }
}

