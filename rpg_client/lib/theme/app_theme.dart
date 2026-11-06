import 'package:flutter/material.dart';

/// Динамическая тема приложения: цветовая схема зависит от выбранного мира.
/// Дефолт (null / forgotten_realms / неизвестный ключ) — классическая фэнтези-тема.
class AppTheme {
  // ─── Базовые цвета (используются по всему коду) ───
  static const Color parchment = Color(0xFFF5E6D3);
  static const Color darkBrown = Color(0xFF3E2723);
  static const Color leather = Color(0xFF8D6E63);
  static const Color gold = Color(0xFFFFD700);
  static const Color bloodRed = Color(0xFFB71C1C);
  static const Color background = Color(0xFF1A1A1A);

  /// Дефолтная (фэнтези) тема — retained for backward compatibility.
  static final ThemeData darkTheme = _build(
    primary: 0xFFFFD700, secondary: 0xFF8D6E63, surface: 0xFF3E2723,
    onSurface: 0xFFF5E6D3, bg: 0xFF1A1A1A,
  );

  /// Тема под конкретный мир. Неизвестные ключи наследуют дефолт.
  static ThemeData forWorld(String? worldKey) {
    switch (worldKey) {
      case 'techno_fantasy':
        return _build(primary: 0xFF29B6F6, secondary: 0xFF78909C, surface: 0xFF1A237E, onSurface: 0xFFB3E5FC, bg: 0xFF0D1B2A);
      case 'steampunk':
        return _build(primary: 0xFFC9A96E, secondary: 0xFF8D6E63, surface: 0xFF3E2723, onSurface: 0xFFFFF8E1, bg: 0xFF1A1410);
      case 'diesel_punk':
        return _build(primary: 0xFF9E9D24, secondary: 0xFFBF360C, surface: 0xFF37474F, onSurface: 0xFFD4E157, bg: 0xFF1B1B1B);
      case 'orbital':
        return _build(primary: 0xFFECEFF1, secondary: 0xFF1565C0, surface: 0xFF0D47A1, onSurface: 0xFFCFD8DC, bg: 0xFF0A0A1A);
      case 'solar_system':
        return _build(primary: 0xFFE53935, secondary: 0xFFFFD700, surface: 0xFF4E342E, onSurface: 0xFFFFCCBC, bg: 0xFF1A0A0A);
      case 'ravenloft':
        return _build(primary: 0xFF7B1FA2, secondary: 0xFF616161, surface: 0xFF000000, onSurface: 0xFF9E9E9E, contentBg: 0xFF000000, bg: 0xFF0D0D0D);
      case 'cyberpunk_2077':
        return _build(primary: 0xFFFFEA00, secondary: 0xFF00E5FF, surface: 0xFF000000, onSurface: 0xFFB0BEC5, bg: 0xFF0A0A0A);
      case 'nuclear_wasteland':
        return _build(primary: 0xFF76FF03, secondary: 0xFFFF6D00, surface: 0xFF263238, onSurface: 0xFFCCFF90, bg: 0xFF1A1A0A);
      case 'infected_world':
        return _build(primary: 0xFF558B2F, secondary: 0xFFBF360C, surface: 0xFF1B5E20, onSurface: 0xFF8BC34A, bg: 0xFF0D1A0D);
      case 'machine_world':
        return _build(primary: 0xFF00BCD4, secondary: 0xFFFFFFFF, surface: 0xFF37474F, onSurface: 0xFF80DEEA, bg: 0xFF0A0A0A);
      case 'warhammer_40k':
        return _build(primary: 0xFFD50000, secondary: 0xFFFFD700, surface: 0xFF000000, onSurface: 0xFFFFD700, contentBg: 0xFF000000, bg: 0xFF0A0000);
      case 'dark_fantasy':
        return _build(primary: 0xFFB71C1C, secondary: 0xFF4A148C, surface: 0xFF212121, onSurface: 0xFFBDBDBD, bg: 0xFF0D0D0D);
      case 'five_systems':
        return _build(primary: 0xFF3F51B5, secondary: 0xFFB0BEC5, surface: 0xFF1A237E, onSurface: 0xFFB39DDB, bg: 0xFF0A0D1A);
      case 'deep_space':
        return _build(primary: 0xFF9C27B0, secondary: 0xFFFFD700, surface: 0xFF311B92, onSurface: 0xFFCE93D8, bg: 0xFF0A0014);
      case 'modern_earth':
        return _build(primary: 0xFFFFFFFF, secondary: 0xFF1976D2, surface: 0xFF424242, onSurface: 0xFFEEEEEE, bg: 0xFF1A1A1A);
      default:
        return darkTheme;
    }
  }

  /// Универсальный конструктор темы. Все свойства согласованы с базовой темой.
  static ThemeData _build({
    required int primary,
    required int secondary,
    required int surface,
    required int onSurface,
    int contentBg = 0xFF3E2723,
    required int bg,
  }) {
    final p = Color(primary);
    final s = Color(secondary);
    final surf = Color(surface);
    final onSurf = Color(onSurface);
    final contentBgColor = Color(contentBg);
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.dark(
        primary: p,
        secondary: s,
        surface: surf,
        onPrimary: _contrast(p),
        onSecondary: _contrast(s),
        onSurface: onSurf,
      ),
      scaffoldBackgroundColor: Color(bg),
      appBarTheme: AppBarTheme(
        backgroundColor: surf,
        foregroundColor: p,
        elevation: 4,
        titleTextStyle: TextStyle(
          fontFamily: 'serif',
          fontSize: 20,
          fontWeight: FontWeight.bold,
          color: p,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        labelStyle: TextStyle(color: p.withValues(alpha: 0.7)),
        hintStyle: TextStyle(color: onSurf.withValues(alpha: 0.4)),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: p.withValues(alpha: 0.3)),
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: p, width: 2),
          borderRadius: BorderRadius.circular(8),
        ),
        filled: true,
        fillColor: Colors.black.withValues(alpha: 0.3),
      ),
      textTheme: TextTheme(
        bodyLarge: TextStyle(fontFamily: 'serif', fontSize: 16, color: onSurf),
        bodyMedium: TextStyle(fontFamily: 'serif', fontSize: 14, color: onSurf),
      ),
      // Диалоги/карточки/шторки согласованы с поверхностью мира
      dialogTheme: DialogThemeData(backgroundColor: contentBgColor),
      cardTheme: CardThemeData(color: contentBgColor.withValues(alpha: 0.55)),
      bottomSheetTheme: BottomSheetThemeData(backgroundColor: contentBgColor),
    );
  }

  static Color _contrast(Color c) => c.computeLuminance() > 0.5 ? Colors.black : Colors.white;
}
