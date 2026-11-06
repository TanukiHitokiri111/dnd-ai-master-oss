import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../theme/app_theme.dart';

/// Провайдер текущей темы. По умолчанию — классическая фэнтези-тема.
/// При выборе мира в создании персонажа тема меняется через
/// [setWorldTheme] (см. CharacterMasterScreen._onWorldSelected).
final themeProvider = NotifierProvider<ThemeNotifier, ThemeData>(ThemeNotifier.new);

class ThemeNotifier extends Notifier<ThemeData> {
  @override
  ThemeData build() => AppTheme.darkTheme;

  /// Установить тему по ключу мира (null — вернуть дефолт).
  void setWorldTheme(String? worldKey) {
    state = AppTheme.forWorld(worldKey);
  }
}
