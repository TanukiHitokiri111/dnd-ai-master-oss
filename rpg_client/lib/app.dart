import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'providers/auth_provider.dart';
import 'providers/api_service_provider.dart';
import 'providers/theme_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/character_master_screen.dart';
import 'screens/inventory_screen.dart';
import 'screens/quests_screen.dart';
import 'screens/map_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/status_screen.dart';
import 'screens/session_lobby_screen.dart';
import 'screens/session_chat_screen.dart';
import 'screens/payment_screen.dart';
import 'models/multiplayer_models.dart';
import 'services/chat_api_service.dart';
import 'theme/app_theme.dart';

class RPGApp extends ConsumerStatefulWidget {
  const RPGApp({super.key});

  @override
  ConsumerState<RPGApp> createState() => _RPGAppState();
}

class _RPGAppState extends ConsumerState<RPGApp> {
  bool _failoverShown = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final api = ref.read(chatApiServiceProvider);
      api.failoverNotifier.addListener(_onFailover);
      // Проверяем сохранённый токен
      ref.read(authProvider.notifier).tryAutoLogin();
    });
  }

  void _onFailover() {
    if (!mounted || _failoverShown) return;
    final api = ref.read(chatApiServiceProvider);
    if (api.failoverNotifier.value != null) {
      _failoverShown = true;
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF1a1a2e),
          title: const Row(children: [
            Icon(Icons.warning_amber, color: Colors.orange, size: 28),
            SizedBox(width: 12),
            Text('Переключение сервера', style: TextStyle(color: Colors.white, fontSize: 18)),
          ]),
          content: const Text(
            'Основной сервер недоступен.\nПереключаюсь на резервный.',
            style: TextStyle(color: Color(0xFF8b949e), fontSize: 14),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('OK', style: TextStyle(color: Color(0xFFc9a96e))),
            ),
          ],
        ),
      );
    }
  }

  @override
  void dispose() {
    final api = ref.read(chatApiServiceProvider);
    api.failoverNotifier.removeListener(_onFailover);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);

    return MaterialApp(
      title: 'D&D AI Master',
      debugShowCheckedModeBanner: false,
      // Тема зависит от выбранного мира (шаг 0 создания персонажа)
      theme: ref.watch(themeProvider),
      // Пока проверяем сохранённую сессию — показываем сплеш
      home: auth.isCheckingSession
          ? const _SplashScreen()
          : (auth.isLoggedIn ? const HomeScreen() : const LoginScreen()),
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case '/login':
            return MaterialPageRoute(builder: (_) => const LoginScreen());
          case '/home':
            return MaterialPageRoute(builder: (_) => const HomeScreen());
          case '/characters':
            return MaterialPageRoute(builder: (_) => const HomeScreen());
          case '/character_create':
            return MaterialPageRoute(builder: (_) => const CharacterMasterScreen(mode: CreateMode.quick));
          case '/character_wizard':
            return MaterialPageRoute(builder: (_) => const CharacterMasterScreen(mode: CreateMode.full));
          case '/inventory':
            final args = settings.arguments as Map<String, dynamic>;
            final itemsJson = args['itemsJson'] as String?;
            List<ItemData> preloaded = [];
            if (itemsJson != null) {
              try {
                final list = json.decode(itemsJson) as List;
                preloaded = list.map((j) => ItemData.fromJson(j as Map<String, dynamic>)).toList();
              } catch (_) {}
            }
            return MaterialPageRoute(
              builder: (_) => InventoryScreen(
                characterId: args['characterId'] as String,
                characterName: args['characterName'] as String,
                gold: args['gold'] as int? ?? 0,
                preloadedItems: preloaded,
              ),
            );
          case '/status':
            final args = settings.arguments as Map<String, String>;
            return MaterialPageRoute(
              builder: (_) => StatusScreen(
                characterId: args['characterId']!,
                characterName: args['characterName']!,
              ),
            );
          case '/chat':
            return MaterialPageRoute(builder: (_) => const ChatScreen());
          case '/session_lobby':
            final session = settings.arguments as SessionData;
            return MaterialPageRoute(builder: (_) => SessionLobbyScreen(session: session));
          case '/session_chat':
            final sessionId = settings.arguments as String;
            return MaterialPageRoute(builder: (_) => SessionChatScreen(sessionId: sessionId));
          case '/payment':
            return MaterialPageRoute(builder: (_) => const PaymentScreen());
          case '/quests':
            final args = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
              builder: (_) => QuestsScreen(
                characterId: args['characterId'] as String,
                characterName: args['characterName'] as String,
              ),
            );
          case '/map':
            final args = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
              builder: (_) => MapScreen(
                characterId: args['characterId'] as String,
                characterName: args['characterName'] as String,
              ),
            );
          default:
            return MaterialPageRoute(builder: (_) => const LoginScreen());
        }
      },
    );
  }
}

/// Заставка на время проверки сохранённой сессии
class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppTheme.darkBrown,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_stories, size: 64, color: AppTheme.gold),
            SizedBox(height: 16),
            SizedBox(width: 32, height: 32, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.gold)),
          ],
        ),
      ),
    );
  }
}
