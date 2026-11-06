import 'dart:async';
import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../models/chat_message.dart';
import '../services/chat_api_service.dart';
import '../services/dice_service.dart';
import 'api_service_provider.dart';

const _uuid = Uuid();

class ChatState {
  final List<ChatMessage> messages;
  final bool isLoading;
  final String? errorMessage;
  final String userId;
  final CharacterData? character;
  final bool leveledUp; // true, когда сервер прислал leveled_up — клиент показывает LevelUpScreen

  const ChatState({this.messages = const [], this.isLoading = false, this.errorMessage, required this.userId, this.character, this.leveledUp = false});

  ChatState copyWith({List<ChatMessage>? messages, bool? isLoading, String? errorMessage, String? userId, CharacterData? character, bool clearCharacter = false, bool? leveledUp}) =>
    ChatState(messages: messages ?? this.messages, isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage, userId: userId ?? this.userId,
      character: clearCharacter ? null : character ?? this.character,
      leveledUp: leveledUp ?? this.leveledUp);
}

class ChatNotifier extends StateNotifier<ChatState> {
  final Ref _ref;
  bool _storageReady = false;

  ChatNotifier(Ref ref) : _ref = ref, super(ChatState(userId: _uuid.v4()));

  Future<void> loadSavedState() async {
    if (_storageReady) return;
    try {
      final storage = await _ref.read(storageServiceProvider.future);
      final storedId = storage.getOrCreateUserId();
      final storedMessages = storage.loadMessages();
      state = state.copyWith(userId: storedId, messages: storedMessages);
    } catch (_) {}
    _storageReady = true;
  }

  void setCharacter(CharacterData c) {
    state = state.copyWith(character: c);
  }

  void clearCharacter() {
    state = state.copyWith(clearCharacter: true, leveledUp: false);
  }

  /// Сброс флага левелапа (после показа экрана)
  void consumeLevelUp() {
    if (state.leveledUp) state = state.copyWith(leveledUp: false);
  }

  /// Перечитать персонажа с сервера (после level-up: HP, статы, уровень)
  Future<void> reloadCharacter() async {
    final c = state.character;
    if (c == null) return;
    try {
      final api = _ref.read(chatApiServiceProvider);
      final fresh = await api.getCharacter(c.id);
      state = state.copyWith(character: fresh);
    } catch (_) {}
  }

  Future<void> _persistMessages() async {
    try {
      final storage = await _ref.read(storageServiceProvider.future);
      await storage.saveMessages(state.messages);
    } catch (_) {}
  }

  void _updateCharacter({int? gold, bool? isDead, int? level, int? xp, int? hpCurrent, int? hpMax}) {
    if (state.character == null) return;
    final c = state.character!;
    state = state.copyWith(
      character: CharacterData(
        id: c.id, userId: c.userId, name: c.name,
        race: c.race, className: c.className,
        backgroundName: c.backgroundName, level: level ?? c.level,
        stats: c.stats, hpMax: hpMax ?? c.hpMax, hpCurrent: hpCurrent ?? c.hpCurrent,
        ac: c.ac, initAc: c.initAc, speed: c.speed,
        gold: gold ?? c.gold,
        backstory: c.backstory,
        features: c.features, proficiencies: c.proficiencies,
        skillProficiencies: c.skillProficiencies, languages: c.languages,
        items: c.items, createdAt: c.createdAt, updatedAt: c.updatedAt,
        isDead: isDead ?? c.isDead,
        world: c.world,
      ),
    );
  }

  Future<void> _addMessage(String role, String text, {bool markdown = false, String? imageUrl, String? appearanceUrl, String? npcUrl, String? npcName}) async {
    final message = ChatMessage(id: _uuid.v4(), role: role, content: text, isMarkdown: markdown, timestamp: DateTime.now(), imageUrl: imageUrl, appearanceUrl: appearanceUrl, npcUrl: npcUrl, npcName: npcName);
    state = state.copyWith(messages: [...state.messages, message]);
    await _persistMessages();
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty || state.isLoading) return;
    await loadSavedState();
    await _addMessage('user', text.trim());
    state = state.copyWith(isLoading: true, errorMessage: null);

    try {
      final api = _ref.read(chatApiServiceProvider);
      final result = await api.sendMessage(
        userId: state.userId, message: text.trim(),
        characterId: state.character?.id,
      );
      await _addMessage('assistant', result.reply, markdown: true, imageUrl: result.imageUrl, appearanceUrl: result.appearanceUrl, npcUrl: result.npcUrl, npcName: result.npcName);

      _applyServerState(result);

      state = state.copyWith(isLoading: false);
    } on ChatApiException catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.message);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: 'Ошибка: $e');
    }
  }

  /// Стриминговая отправка: текст печатается по мере генерации,
  /// теги обрабатываются сервером в конце (done-событие).
  Future<void> sendMessageStream(String text) async {
    if (text.trim().isEmpty || state.isLoading) return;
    await loadSavedState();
    await _addMessage('user', text.trim());
    state = state.copyWith(isLoading: true, errorMessage: null);

    // Добавляем "заглушку" ответа — в неё будут аппендиться чанки
    final msgId = _uuid.v4();
    final placeholder = ChatMessage(id: msgId, role: 'assistant', content: '', isMarkdown: true, timestamp: DateTime.now());
    state = state.copyWith(messages: [...state.messages, placeholder]);
    await _persistMessages();

    var buffer = '';
    ChatSendResult? finalResult;
    // Typewriter-эффект: сервер шлёт чанки абзацами (модель так отдаёт) —
    // если аппендить их напрямую, текст появляется скачками. Накопленный
    // текст кладём в очередь и «печатаем» мелкими кусочками по таймеру,
    // чтобы выглядело как живой набор текста в реальном времени.
    var queue = '';
    Timer? typeTimer;
    var doneReceived = false;

    void pumpQueue() {
      if (queue.isEmpty) return;
      // За один тик печатаем 3 символа (~100 симв/с) — плавно, но не тянется
      final take = queue.length >= 3 ? 3 : queue.length;
      buffer += queue.substring(0, take);
      queue = queue.substring(take);
      final updated = ChatMessage(
        id: msgId, role: 'assistant', content: buffer, isMarkdown: true,
        timestamp: DateTime.now(), streaming: true,
      );
      state = state.copyWith(messages: [
        for (final m in state.messages) m.id == msgId ? updated : m,
      ]);
    }

    void startTypeTimer() {
      typeTimer?.cancel();
      typeTimer = Timer.periodic(const Duration(milliseconds: 30), (_) => pumpQueue());
    }

    void stopTypeTimer() {
      typeTimer?.cancel();
      typeTimer = null;
    }

    try {
      final api = _ref.read(chatApiServiceProvider);
      await for (final event in api.streamMessage(
        userId: state.userId, message: text.trim(),
        characterId: state.character?.id,
      )) {
        switch (event) {
          case ChatStreamDelta(:final text):
            queue += text;
            if (typeTimer == null) startTypeTimer();
          case ChatStreamDone(:final result):
            finalResult = result;
            doneReceived = true;
          case ChatStreamError(:final message):
            state = state.copyWith(errorMessage: message);
        }
      }

      // Допечатываем всё что осталось в очереди
      while (queue.isNotEmpty && !doneReceived) {
        await Future.delayed(const Duration(milliseconds: 30));
        pumpQueue();
      }
      stopTypeTimer();
      // done пришёл раньше, чем очередь допечаталась — выплёскиваем остаток
      if (queue.isNotEmpty) {
        buffer += queue;
        queue = '';
        final updated = ChatMessage(
          id: msgId, role: 'assistant', content: buffer, isMarkdown: true,
          timestamp: DateTime.now(), streaming: true,
        );
        state = state.copyWith(messages: [
          for (final m in state.messages) m.id == msgId ? updated : m,
        ]);
      }

      // Финализируем: заменяем placeholder на готовое сообщение с картинками
      final done = finalResult;
      final fullText = (done?.reply.isNotEmpty ?? false) ? done!.reply : buffer;
      final finalMsg = ChatMessage(
        id: msgId, role: 'assistant', content: fullText, isMarkdown: true,
        timestamp: DateTime.now(), streaming: false,
        imageUrl: done?.imageUrl, appearanceUrl: done?.appearanceUrl,
        npcUrl: done?.npcUrl, npcName: done?.npcName,
      );
      state = state.copyWith(messages: [
        for (final m in state.messages) m.id == msgId ? finalMsg : m,
      ]);
      await _persistMessages();

      if (done != null) _applyServerState(done);

      state = state.copyWith(isLoading: false);
    } on ChatApiException catch (e) {
      stopTypeTimer();
      // Если ответ уже частично напечатан — сохраняем его, не выбрасываем
      ChatMessage? partialMsg;
      for (final m in state.messages) {
        if (m.id == msgId) { partialMsg = m; break; }
      }
      final hasPartial = partialMsg != null && partialMsg.content.trim().isNotEmpty;
      state = state.copyWith(
        isLoading: false, errorMessage: e.message,
        messages: [
          for (final m in state.messages)
            if (m.id == msgId)
              (hasPartial
                  ? ChatMessage(
                      id: msgId, role: 'assistant', content:
                          '${partialMsg.content}\n\n_⚠️ Соединение прервано — ответ мог оборваться. Нажмите «💬» и отправьте сообщение ещё раз, чтобы продолжить._',
                      isMarkdown: true, timestamp: DateTime.now(), streaming: false)
                  : m)
              else m,
        ],
      );
    } catch (e) {
      stopTypeTimer();
      ChatMessage? partialMsg;
      for (final m in state.messages) {
        if (m.id == msgId) { partialMsg = m; break; }
      }
      final hasPartial = partialMsg != null && partialMsg.content.trim().isNotEmpty;
      state = state.copyWith(
        isLoading: false, errorMessage: 'Ошибка: $e',
        messages: [
          for (final m in state.messages)
            if (m.id == msgId)
              (hasPartial
                  ? ChatMessage(
                      id: msgId, role: 'assistant', content:
                          '${partialMsg.content}\n\n_⚠️ Соединение прервано — ответ мог оборваться. Нажмите «💬» и отправьте сообщение ещё раз, чтобы продолжить._',
                      isMarkdown: true, timestamp: DateTime.now(), streaming: false)
                  : m)
              else m,
        ],
      );
    }
  }

  void _applyServerState(ChatSendResult result) {
    // Обновляем золото если изменилось
    if (result.gold != null) _updateCharacter(gold: result.gold);

    // HP если изменилось
    if (result.hpCurrent != null && result.hpMax != null) {
      _updateCharacter(hpCurrent: result.hpCurrent, hpMax: result.hpMax);
    }

    // Если персонаж умер / воскрес — обновляем флаг
    _updateCharacter(isDead: result.isDead);

    // Если сервер начислил опыт / поднял уровень — обновляем и показываем экран
    if (result.level != null) _updateCharacter(level: result.level, xp: result.xp);
    if (result.leveledUp) {
      state = state.copyWith(leveledUp: true);
    }
  }

  Future<void> rollDice(int sides, {int modifier = 0, String label = '', bool sendToServer = true, int count = 1, bool advantage = false, bool disadvantage = false}) async {
    if (sendToServer && state.character != null) {
      // Сервер сам бросает кубики и клампит модификатор по статам — клиентские
      // результаты НЕ показываем как истину, ждём dice_roll из ответа сервера.
      state = state.copyWith(isLoading: true);
      try {
        final api = _ref.read(chatApiServiceProvider);
        final diceData = DiceRollData(
          dice: List.filled(count, sides),
          results: const [], // сервер перебросит
          modifier: modifier,
          label: label,
          advantage: advantage,
          disadvantage: disadvantage,
        );
        final result = await api.sendMessage(
          userId: state.userId, message: label.isNotEmpty ? label : (count > 1 ? 'Бросок ${count}d$sides' : 'Бросок'),
          characterId: state.character?.id, diceRoll: diceData,
        );
        // Показываем СЕРВЕРНЫЙ результат броска (анти-чит: клиент не диктует)
        if (result.diceRoll != null) {
          await _addMessage('system', DiceService.formatServerRoll(result.diceRoll!), markdown: true);
        }
        await _addMessage('assistant', result.reply, markdown: true, imageUrl: result.imageUrl, appearanceUrl: result.appearanceUrl, npcUrl: result.npcUrl, npcName: result.npcName);
        if (result.gold != null) _updateCharacter(gold: result.gold);
      } on ChatApiException catch (e) {
        state = state.copyWith(errorMessage: e.message);
      } catch (_) {}
      state = state.copyWith(isLoading: false);
      return;
    }

    // Офлайн-режим / без персонажа: локальный бросок как раньше
    if (count > 1) {
      // Мульти-кубик: NdX
      final results = DiceService.rollMultiple(count, sides);
      await _addMessage('system', DiceService.formatMultiRoll(count, sides, results, modifier: modifier, label: label), markdown: true);
    } else if (advantage || disadvantage) {
      // Бросок с преимуществом / помехой: 2d20 берём max/min
      final result1 = DiceService.roll(sides);
      final result2 = DiceService.roll(sides);
      final bestResult = advantage ? max(result1, result2) : min(result1, result2);
      await _addMessage('system', DiceService.formatRoll(sides, bestResult,
        modifier: modifier, label: label,
        advantage: advantage, disadvantage: disadvantage,
        secondResult: advantage ? min(result1, result2) : max(result1, result2),
      ), markdown: true);
    } else {
      // Одиночный кубик
      final result = DiceService.roll(sides);
      await _addMessage('system', DiceService.formatRoll(sides, result, modifier: modifier, label: label), markdown: true);
    }
  }

  void clearError() => state = state.copyWith(errorMessage: null);

  Future<void> clearChat() async {
    final api = _ref.read(chatApiServiceProvider);
    try { await api.clearHistory(state.userId); } catch (_) {}
    try {
      final storage = await _ref.read(storageServiceProvider.future);
      await storage.clearMessages();
      await storage.resetUserId();
      final newId = storage.getOrCreateUserId();
      state = ChatState(userId: newId, character: state.character);
    } catch (_) {
      state = ChatState(userId: _uuid.v4(), character: state.character);
    }
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) => ChatNotifier(ref));
