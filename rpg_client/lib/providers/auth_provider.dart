import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../services/storage_service.dart';
import 'api_service_provider.dart';

class AuthState {
  final bool isLoggedIn;
  final String? token;
  final String? userId;
  final String? username;
  final String? error;
  final bool isLoading;
  final bool isCheckingSession;
  final String? boostyLogin;
  final String? subscriptionTier;
  const AuthState({this.isLoggedIn = false, this.token, this.userId, this.username, this.error, this.isLoading = false, this.isCheckingSession = false, this.boostyLogin, this.subscriptionTier});
  AuthState copyWith({bool? isLoggedIn, String? token, String? userId, String? username, String? error, bool? isLoading, bool? isCheckingSession, String? boostyLogin, String? subscriptionTier, bool clearError = false}) =>
    AuthState(isLoggedIn: isLoggedIn ?? this.isLoggedIn, token: token ?? this.token, userId: userId ?? this.userId,
      username: username ?? this.username, error: clearError ? null : error, isLoading: isLoading ?? this.isLoading,
      isCheckingSession: isCheckingSession ?? this.isCheckingSession,
      boostyLogin: boostyLogin ?? this.boostyLogin,
      subscriptionTier: subscriptionTier ?? this.subscriptionTier);
}

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;
  AuthNotifier(this._ref) : super(const AuthState());

  /// Проверить сохранённый токен при старте приложения
  Future<void> tryAutoLogin() async {
    state = state.copyWith(isCheckingSession: true);
    try {
      final storage = await _ref.read(storageServiceProvider.future);
      final saved = storage.loadAuth();
      if (saved == null) {
        state = state.copyWith(isCheckingSession: false);
        return;
      }
      final token = saved['token']!;
      final userId = saved['user_id']!;
      final username = saved['username'];
      final api = _ref.read(chatApiServiceProvider);
      api.token = token;
      try {
        await api.listCharacters();
      } on ChatApiException catch (e) {
        if (e.statusCode == 401) {
          await storage.clearAuth();
          api.token = null;
          state = state.copyWith(isCheckingSession: false);
          return;
        }
      }
      state = AuthState(isLoggedIn: true, token: token, userId: userId, username: username);
      unawaited(_fetchAuthStatus());
    } catch (_) {
      state = state.copyWith(isCheckingSession: false);
    }
  }

  Future<void> _fetchAuthStatus() async {
    try {
      final api = _ref.read(chatApiServiceProvider);
      final status = await api.authStatus();
      state = state.copyWith(
        boostyLogin: status['boosty_login'] as String?,
        subscriptionTier: status['subscription_tier'] as String?,
      );
    } catch (_) {}  // silently ignore — non-critical
  }

  Future<bool> register(String username, String password, [String? boostyLogin]) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final api = _ref.read(chatApiServiceProvider);
      final r = await api.register(username, password, boostyLogin);
      final token = r['token'] as String;
      final userId = r['user_id'] as String;
      api.token = token;
      final storage = await _ref.read(storageServiceProvider.future);
      await storage.saveAuth(token, userId, username);
      state = AuthState(isLoggedIn: true, token: token, userId: userId, username: username);
      unawaited(_fetchAuthStatus());
      return true;
    } on ChatApiException catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
      return false;
    }
  }

  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final api = _ref.read(chatApiServiceProvider);
      final r = await api.login(username, password);
      final token = r['token'] as String;
      final userId = r['user_id'] as String;
      api.token = token;
      final storage = await _ref.read(storageServiceProvider.future);
      await storage.saveAuth(token, userId, username);
      state = AuthState(isLoggedIn: true, token: token, userId: userId, username: username);
      unawaited(_fetchAuthStatus());
      return true;
    } on ChatApiException catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
      return false;
    }
  }

  Future<String?> linkBoosty(String boostyLogin) async {
    try {
      final api = _ref.read(chatApiServiceProvider);
      final r = await api.linkBoosty(boostyLogin);
      unawaited(_fetchAuthStatus());  // update UI immediately
      return r['old_user_deactivated'] == true
        ? 'Boosty привязан! Старый аккаунт деактивирован.'
        : 'Boosty привязан!';
    } on ChatApiException catch (e) {
      return 'Ошибка: ${e.message}';
    }
  }

  Future<String?> redeemCode(String code) async {
    try {
      final api = _ref.read(chatApiServiceProvider);
      final r = await api.redeemCode(code);
      return 'Код активирован! Доступ открыт до ${r['expires_at'] ?? "неизвестно"}.';
    } on ChatApiException catch (e) {
      return 'Ошибка: ${e.message}';
    }
  }

  Future<void> logout() async {
    _ref.read(chatApiServiceProvider).token = null;
    try {
      final storage = await _ref.read(storageServiceProvider.future);
      await storage.clearAuth();
    } catch (_) {}
    state = const AuthState();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) => AuthNotifier(ref));
