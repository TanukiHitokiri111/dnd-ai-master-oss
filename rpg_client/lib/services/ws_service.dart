import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/app_config.dart';

/// События из WebSocket
class WsEvent {
  final String type;
  final Map<String, dynamic> data;
  const WsEvent({required this.type, required this.data});
}

/// Сервис WebSocket для игровой сессии.
/// Подключается к ws://host/api/v1/ws/{session_id}?token=***
/// Автоматический reconnect с exponential backoff.
class WsService {
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  final String _baseUrl;
  final _controller = StreamController<WsEvent>.broadcast();
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  String? _sessionId;
  String? _token;
  bool _disposed = false;
  bool _intentionalDisconnect = false;
  int _reconnectAttempt = 0;
  static const int _maxReconnectDelay = 30; // секунд
  static const int _pingInterval = 20;

  WsService({String? baseUrl}) : _baseUrl = baseUrl ?? AppConfig.baseUrl;

  Stream<WsEvent> get events => _controller.stream;

  Future<void> connect(String sessionId, String token) async {
    // Отменить старую подписку при переподключении — иначе дубли обработчиков
    await _subscription?.cancel();
    _subscription = null;
    _sessionId = sessionId;
    _token = token;
    _intentionalDisconnect = false;
    _reconnectAttempt = 0;

    await _doConnect();
  }

  Future<void> _doConnect() async {
    if (_disposed || _sessionId == null || _token == null) return;

    try {
      final wsUrl = _baseUrl
          .replaceFirst('http://', 'ws://')
          .replaceFirst('https://', 'wss://');
      final uri = Uri.parse('$wsUrl${AppConfig.apiVersion}/ws/${_sessionId}?token=${_token}');

      _channel = WebSocketChannel.connect(uri);

      _subscription = _channel!.stream.listen(
        (raw) {
          if (_disposed) return;
          // Сброс счётчика реконнекта при успешном получении данных
          _reconnectAttempt = 0;
          try {
            final data = json.decode(raw as String) as Map<String, dynamic>;
            final type = data['type'] as String? ?? 'unknown';
            _controller.add(WsEvent(type: type, data: data));
          } catch (_) {}
        },
        onError: (e) {
          if (!_disposed) _controller.addError(e);
          _scheduleReconnect();
        },
        onDone: () {
          if (!_disposed && !_intentionalDisconnect) {
            _controller.add(const WsEvent(type: 'disconnected', data: {}));
            _scheduleReconnect();
          }
        },
        cancelOnError: false,
      );

      // Пинг каждые 20 сек чтобы не отвалиться
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(const Duration(seconds: _pingInterval), (_) {
        send({'type': 'ping'});
      });
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed || _intentionalDisconnect || _sessionId == null) return;

    _reconnectTimer?.cancel();
    // Exponential backoff: 1, 2, 4, 8, 16, 30, 30, 30...
    final delay = (_reconnectAttempt < 5)
        ? (1 << _reconnectAttempt) // 1, 2, 4, 8, 16
        : _maxReconnectDelay;
    _reconnectAttempt++;

    debugPrint('🔌 WS reconnect in ${delay}s (attempt $_reconnectAttempt)');
    _reconnectTimer = Timer(Duration(seconds: delay), () {
      _cleanup();
      _doConnect();
    });
  }

  void _cleanup() {
    _pingTimer?.cancel();
    _pingTimer = null;
    try { _channel?.sink.close(); } catch (_) {}
    _channel = null;
  }

  void send(Map<String, dynamic> data) {
    try {
      _channel?.sink.add(json.encode(data));
    } catch (_) {}
  }

  void sendChat(String content, {String? characterId, Map<String, dynamic>? diceRoll}) {
    send({
      'type': 'chat',
      'content': content,
      if (characterId != null) 'character_id': characterId,
      if (diceRoll != null) 'dice_roll': diceRoll,
    });
  }

  void sendTurnChange(String action) {
    send({'type': 'turn_change', 'action': action});
  }

  void disconnect() {
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _cleanup();
    _subscription?.cancel();
    _subscription = null;
    _sessionId = null;
    _token = null;
  }

  bool get isConnected => _channel != null;

  void dispose() {
    _disposed = true;
    disconnect();
    _controller.close();
  }
}