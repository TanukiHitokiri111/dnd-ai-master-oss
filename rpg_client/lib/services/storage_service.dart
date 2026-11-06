/// Conditional re-export StorageService:
/// - Web:     storage_service_web.dart   (window.localStorage, dart:html)
/// - Mobile:  storage_service_io.dart    (shared_preferences)
library storage_service;

export 'storage_service_io.dart'
    if (dart.library.html) 'storage_service_web.dart';
