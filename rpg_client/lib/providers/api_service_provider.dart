import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../services/storage_service.dart';
import '../config/app_config.dart';

final chatApiServiceProvider = Provider<ChatApiService>((ref) {
  final service = ChatApiService(
    baseUrl: AppConfig.baseUrl,
  );
  ref.onDispose(service.dispose);
  return service;
});

/// Ленивый StorageService — создаётся сам при первом обращении
final storageServiceProvider = FutureProvider<StorageService>((ref) async {
  return await StorageService.create();
});
