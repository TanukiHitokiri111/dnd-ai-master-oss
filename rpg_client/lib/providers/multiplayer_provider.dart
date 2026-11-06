import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/multiplayer_models.dart';
import '../services/chat_api_service.dart';
import '../services/ws_service.dart';
import 'api_service_provider.dart';

/// Состояние мультиплеера
class MultiplayerState {
  final List<SessionData> sessions;
  final List<FriendData> friends;
  final List<FriendData> pendingFriends;
  final List<GameMessage> messages;
  final SessionData? currentSession;
  final bool isLoading;
  final String? error;
  final bool wsConnected;
  final bool aiTyping;
  final String? turnError;  // NOT_YOUR_TURN и подобные

  const MultiplayerState({
    this.sessions = const [],
    this.friends = const [],
    this.pendingFriends = const [],
    this.messages = const [],
    this.currentSession,
    this.isLoading = false,
    this.error,
    this.wsConnected = false,
    this.aiTyping = false,
    this.turnError,
  });

  MultiplayerState copyWith({
    List<SessionData>? sessions,
    List<FriendData>? friends,
    List<FriendData>? pendingFriends,
    List<GameMessage>? messages,
    SessionData? currentSession,
    bool? isLoading,
    String? error,
    bool? wsConnected,
    bool? aiTyping,
    String? turnError,
  }) => MultiplayerState(
    sessions: sessions ?? this.sessions,
    friends: friends ?? this.friends,
    pendingFriends: pendingFriends ?? this.pendingFriends,
    messages: messages ?? this.messages,
    currentSession: currentSession ?? this.currentSession,
    isLoading: isLoading ?? this.isLoading,
    error: error,
    wsConnected: wsConnected ?? this.wsConnected,
    aiTyping: aiTyping ?? this.aiTyping,
    turnError: turnError,
  );
}

class MultiplayerNotifier extends StateNotifier<MultiplayerState> {
  final ChatApiService _api;
  final WsService _ws = WsService();
  StreamSubscription<WsEvent>? _wsSub;
  String? _userId;

  MultiplayerNotifier(this._api) : super(const MultiplayerState());

  void setUserId(String uid) => _userId = uid;

  // ── Sessions CRUD ──

  Future<void> loadSessions() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final raw = await _api.listSessions();
      state = state.copyWith(
        sessions: raw.map((j) => SessionData.fromJson(j)).toList(),
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: '$e');
    }
  }

  Future<SessionData?> createSession(String name) async {
    try {
      final raw = await _api.createSession(name);
      final s = SessionData.fromJson(raw);
      await loadSessions();
      return s;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return null;
    }
  }

  Future<bool> joinSession(String code) async {
    try {
      await _api.joinSession(code);
      await loadSessions();
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<void> refreshSession(String id) async {
    try {
      final raw = await _api.getSession(id);
      state = state.copyWith(currentSession: SessionData.fromJson(raw));
    } catch (_) {}
  }

  Future<bool> setReady(String sessionId, String characterId) async {
    try {
      await _api.setReady(sessionId, characterId);
      await refreshSession(sessionId);
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> startSession(String id) async {
    try {
      await _api.startSession(id);
      await refreshSession(id);
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> rollInitiative(String id) async {
    try {
      await _api.rollInitiative(id);
      await refreshSession(id);
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> leaveSession(String id) async {
    try {
      await _api.leaveSession(id);
      state = state.copyWith(currentSession: null, messages: []);
      await loadSessions();
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> deleteSession(String id) async {
    try {
      final ok = await _api.deleteSession(id);
      if (ok) await loadSessions();
      return ok;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  // ── WebSocket ──

  Future<void> connectWs(String sessionId, String token) async {
    _wsSub?.cancel();
    _wsSub = _ws.events.listen(_onWsEvent);
    try {
      await _ws.connect(sessionId, token);
      state = state.copyWith(wsConnected: true);
      debugPrint('🔌 connectWs OK: session=$sessionId');
    } catch (e, st) {
      debugPrint('❌ connectWs FAILED: $e\n$st');
    }
  }

  void _onWsEvent(WsEvent event) {
    switch (event.type) {
      case 'game_message':
        final msg = GameMessage.fromJson(event.data);
        state = state.copyWith(
          messages: [...state.messages, msg],
          aiTyping: false,
        );
        break;
      case 'connected':
        state = state.copyWith(wsConnected: true);
        break;
      case 'user_connected':
      case 'user_disconnected':
        if (state.currentSession != null) {
          refreshSession(state.currentSession!.id);
        }
        break;
      case 'turn_change':
        if (state.currentSession != null) {
          refreshSession(state.currentSession!.id);
        }
        break;
      case 'pong':
        break;
      case 'error':
        final code = event.data['code'] as String? ?? '';
        final message = event.data['message'] as String? ?? 'Ошибка сервера';
        if (code == 'NOT_YOUR_TURN') {
          state = state.copyWith(turnError: message, aiTyping: false);
        } else {
          state = state.copyWith(error: message, aiTyping: false);
        }
        break;
      case 'disconnected':
        state = state.copyWith(wsConnected: false);
        break;
    }
  }

  void sendChat(String content, {String? characterId, Map<String, dynamic>? diceRoll}) {
    if (content.trim().isEmpty) return;
    _ws.sendChat(content, characterId: characterId, diceRoll: diceRoll);
    state = state.copyWith(aiTyping: true);
  }

  void sendTurnChange(String action) => _ws.sendTurnChange(action);

  Future<void> loadMessages(String sessionId) async {
    try {
      final raw = await _api.getSessionMessages(sessionId);
      final msgs = ((raw['messages'] ?? []) as List)
          .map((j) => GameMessage.fromJson(j as Map<String, dynamic>))
          .toList();
      state = state.copyWith(messages: msgs);
      debugPrint('🔄 loadMessages OK: ${msgs.length} msgs for $sessionId');
    } catch (e, st) {
      debugPrint('❌ loadMessages FAILED: $e\n$st');
    }
  }

  void disconnectWs() {
    _wsSub?.cancel();
    _ws.disconnect();
    state = state.copyWith(wsConnected: false);
  }

  // ── Friends ──

  Future<void> loadFriends() async {
    try {
      final raw = await _api.getFriends();
      final all = raw.map((j) => FriendData.fromJson(j)).toList();
      state = state.copyWith(
        friends: all.where((f) => f.status == 'accepted').toList(),
        pendingFriends: all.where((f) => f.status == 'pending').toList(),
      );
    } catch (_) {}
  }

  Future<bool> sendFriendRequest(String username) async {
    try {
      await _api.sendFriendRequest(username);
      return true;
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> searchUsers(String query) async {
    try {
      return await _api.searchUsers(query);
    } catch (_) {
      return [];
    }
  }

  Future<Map<String, dynamic>?> inviteFriendToSession(String sessionId, String friendUserId) async {
    try {
      return await _api.inviteFriendToSession(sessionId, friendUserId);
    } catch (e) {
      state = state.copyWith(error: '$e');
      return null;
    }
  }

  Future<bool> acceptFriend(int requestId) async {
    try {
      return await _api.acceptFriend(requestId);
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> rejectFriend(int requestId) async {
    try {
      return await _api.rejectFriend(requestId);
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  Future<bool> removeFriend(String friendUserId) async {
    try {
      return await _api.removeFriend(friendUserId);
    } catch (e) {
      state = state.copyWith(error: '$e');
      return false;
    }
  }

  void clearError() => state = state.copyWith(error: null);
  void clearTurnError() => state = state.copyWith(turnError: null);

  @override
  void dispose() {
    _ws.dispose();
    _wsSub?.cancel();
    super.dispose();
  }
}

final multiplayerProvider = StateNotifierProvider<MultiplayerNotifier, MultiplayerState>((ref) {
  final api = ref.watch(chatApiServiceProvider);
  return MultiplayerNotifier(api);
});
