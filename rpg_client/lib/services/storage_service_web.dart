/// Веб-реализация хранилища через window.localStorage (dart:html).
/// Ноль зависимостей от shared_preferences.
library storage_service_web;

import 'dart:convert';
import 'dart:html' as html;
import 'package:uuid/uuid.dart';
import '../models/chat_message.dart';
import '../utils/constants.dart';

class StorageService {
  StorageService._();

  static Future<StorageService> create() async => StorageService._();

  String getOrCreateUserId() {
    var id = _get(AppConstants.storageKeyUserId);
    if (id == null) {
      id = const Uuid().v4();
      _set(AppConstants.storageKeyUserId, id);
    }
    return id;
  }

  Future<void> resetUserId() async {
    _set(AppConstants.storageKeyUserId, const Uuid().v4());
  }

  Future<void> saveMessages(List<ChatMessage> messages) async {
    final limited = messages.length > AppConstants.maxStoredMessages
        ? messages.sublist(messages.length - AppConstants.maxStoredMessages)
        : messages;
    final jsonList = limited.map((m) => m.toJson()).toList();
    _set(AppConstants.storageKeyMessages, json.encode(jsonList));
  }

  List<ChatMessage> loadMessages() {
    final raw = _get(AppConstants.storageKeyMessages);
    if (raw == null) return [];
    try {
      final list = json.decode(raw) as List;
      return list
          .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> clearMessages() async {
    _remove(AppConstants.storageKeyMessages);
  }

  // ─── Auth ───

  Future<void> saveAuth(String token, String userId, String username) async {
    _set(AppConstants.storageKeyAuthToken, token);
    _set(AppConstants.storageKeyAuthUserId, userId);
    _set(AppConstants.storageKeyAuthUsername, username);
  }

  Map<String, String?>? loadAuth() {
    final token = _get(AppConstants.storageKeyAuthToken);
    if (token == null || token.isEmpty) return null;
    return {
      'token': token,
      'user_id': _get(AppConstants.storageKeyAuthUserId),
      'username': _get(AppConstants.storageKeyAuthUsername),
    };
  }

  Future<void> clearAuth() async {
    _remove(AppConstants.storageKeyAuthToken);
    _remove(AppConstants.storageKeyAuthUserId);
    _remove(AppConstants.storageKeyAuthUsername);
  }

  // ─── localStorage ───

  String? _get(String key) => html.window.localStorage[key];
  void _set(String key, String value) => html.window.localStorage[key] = value;
  void _remove(String key) => html.window.localStorage.remove(key);
}
