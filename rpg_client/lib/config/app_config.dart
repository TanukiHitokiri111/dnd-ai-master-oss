class AppConfig {
  /// Адрес API. По умолчанию пусто — клиент ходит на тот же хост, с которого
  /// загружен (работает для веб-сборки за обратным прокси на том же порту).
  /// Переопределить при сборке:
  ///   flutter build web --dart-define=API_BASE_URL=https://example.com
  static const String baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
  static const String apiVersion = '/api/v1';
  static const Duration requestTimeout = Duration(seconds: 90);
  /// Чат может генерировать картинки (сцена/внешность) — бэкенд каскадом
  /// ждёт до 240с на картинку + до 120с на AI-ответ. Даём запас на весь каскад.
  static const Duration chatRequestTimeout = Duration(seconds: 360);
}
