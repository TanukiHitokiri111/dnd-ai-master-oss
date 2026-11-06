import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/chat_message.dart';
import '../utils/constants.dart';

class StorageService {
  final SharedPreferences _prefs;
  StorageService(this._prefs);

  static Future<StorageService> create() async {
    return StorageService(await SharedPreferences.getInstance());
  }

  String getOrCreateUserId() {
    var id = _prefs.getString(AppConstants.storageKeyUserId);
    if (id == null) {
      id = const Uuid().v4();
      _prefs.setString(AppConstants.storageKeyUserId, id);
    }
    return id;
  }

  Future<void> resetUserId() async {
    await _prefs.setString(AppConstants.storageKeyUserId, const Uuid().v4());
  }

  Future<void> saveMessages(List<ChatMessage> messages) async {
    final limited = messages.length > AppConstants.maxStoredMessages
        ? messages.sublist(messages.length - AppConstants.maxStoredMessages)
        : messages;
    final jsonList = limited.map((m) => m.toJson()).toList();
    await _prefs.setString(AppConstants.storageKeyMessages, json.encode(jsonList));
  }

  List<ChatMessage> loadMessages() {
    final raw = _prefs.getString(AppConstants.storageKeyMessages);
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
    await _prefs.remove(AppConstants.storageKeyMessages);
  }

  // ─── Auth persistence ───

  Future<void> saveAuth(String token, String userId, String username) async {
    await _prefs.setString(AppConstants.storageKeyAuthToken, token);
    await _prefs.setString(AppConstants.storageKeyAuthUserId, userId);
    await _prefs.setString(AppConstants.storageKeyAuthUsername, username);
  }

  /// null если токена нет (не залогинен)
  Map<String, String?>? loadAuth() {
    final token = _prefs.getString(AppConstants.storageKeyAuthToken);
    if (token == null || token.isEmpty) return null;
    return {
      'token': token,
      'user_id': _prefs.getString(AppConstants.storageKeyAuthUserId),
      'username': _prefs.getString(AppConstants.storageKeyAuthUsername),
    };
  }

  Future<void> clearAuth() async {
    await _prefs.remove(AppConstants.storageKeyAuthToken);
    await _prefs.remove(AppConstants.storageKeyAuthUserId);
    await _prefs.remove(AppConstants.storageKeyAuthUsername);
  }
}
