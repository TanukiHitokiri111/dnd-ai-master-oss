import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../theme/app_theme.dart';
import 'character_screen.dart';
import 'sessions_screen.dart';
import 'friends_screen.dart';
import '../providers/multiplayer_provider.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(multiplayerProvider.notifier).loadFriends();
    });
  }

  @override
  Widget build(BuildContext context) {
    final mp = ref.watch(multiplayerProvider);
    final pendingFriends = mp.pendingFriends.length;

    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: const [
          CharacterScreen(),
          SessionsScreen(),
          FriendsScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _tab,
        onTap: (i) => setState(() => _tab = i),
        backgroundColor: AppTheme.darkBrown,
        selectedItemColor: AppTheme.gold,
        unselectedItemColor: AppTheme.parchment.withValues(alpha: 0.4),
        items: [
          const BottomNavigationBarItem(
            icon: Icon(Icons.person),
            activeIcon: Icon(Icons.person, size: 28),
            label: 'Соло',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.groups),
            activeIcon: Icon(Icons.groups, size: 28),
            label: 'Партия',
          ),
          BottomNavigationBarItem(
            icon: Badge(
              isLabelVisible: pendingFriends > 0,
              label: Text('$pendingFriends', style: const TextStyle(fontSize: 10)),
              child: const Icon(Icons.people),
            ),
            activeIcon: Badge(
              isLabelVisible: pendingFriends > 0,
              label: Text('$pendingFriends', style: const TextStyle(fontSize: 10)),
              child: const Icon(Icons.people, size: 28),
            ),
            label: 'Друзья',
          ),
        ],
      ),
    );
  }
}
