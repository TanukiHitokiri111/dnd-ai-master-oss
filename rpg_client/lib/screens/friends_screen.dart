import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/multiplayer_models.dart';
import '../providers/multiplayer_provider.dart';

class FriendsScreen extends ConsumerStatefulWidget {
  const FriendsScreen({super.key});

  @override
  ConsumerState<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends ConsumerState<FriendsScreen> {
  final _searchCtl = TextEditingController();
  String _searchQuery = '';
  List<Map<String, dynamic>> _searchResults = [];
  bool _searching = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(multiplayerProvider.notifier).loadFriends();
    });
  }

  @override
  void dispose() {
    _searchCtl.dispose();
    super.dispose();
  }

  Future<void> _doSearch() async {
    final q = _searchCtl.text.trim();
    if (q.isEmpty) return;
    setState(() => _searching = true);
    try {
      final results =
          await ref.read(multiplayerProvider.notifier).searchUsers(q);
      if (mounted) setState(() => _searchResults = results);
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<void> _sendRequest(String username) async {
    final ok =
        await ref.read(multiplayerProvider.notifier).sendFriendRequest(username);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ok ? 'Заявка отправлена!' : 'Ошибка отправки заявки'),
        ),
      );
      if (ok) {
        _searchCtl.clear();
        setState(() => _searchResults = []);
        ref.read(multiplayerProvider.notifier).loadFriends();
      }
    }
  }

  Future<void> _inviteFriend(String friendUserId, String username) async {
    final mp = ref.read(multiplayerProvider);
    final sessions = mp.sessions;
    if (sessions.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Создайте сессию, чтобы приглашать друзей')),
      );
      return;
    }

    final session = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: const Text('Пригласить в сессию'),
        children: sessions.map((s) {
          return SimpleDialogOption(
            onPressed: () => Navigator.pop(ctx, {'id': s.id, 'name': s.name}),
            child: Text(s.name, style: const TextStyle(color: Colors.white)),
          );
        }).toList(),
      ),
    );

    if (session != null && mounted) {
      final result = await ref
          .read(multiplayerProvider.notifier)
          .inviteFriendToSession(session['id'], friendUserId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result != null
                ? 'Приглашение отправлено! Код: ${result['invite_code']}'
                : 'Ошибка приглашения'),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final mp = ref.watch(multiplayerProvider);
    final friends = mp.friends;
    final pending = mp.pendingFriends;

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        body: Column(
          children: [
            TabBar(
              labelColor: const Color(0xFFc9a96e),
              unselectedLabelColor: const Color(0xFF8b949e),
              indicatorColor: const Color(0xFFc9a96e),
              tabs: [
              Tab(text: 'Друзья (${friends.length})'),
              Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Заявки'),
                    if (pending.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: Colors.red,
                          borderRadius: BorderRadius.circular(9),
                        ),
                        child: Text(
                          '${pending.length}',
                          style: const TextStyle(color: Colors.white, fontSize: 11),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Tab(text: 'Поиск'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                _buildFriendsTab(friends),
                _buildPendingTab(pending),
                _buildSearchTab(),
              ],
            ),
          ),
        ],
      ),
    ),
    );
  }

  // ── Friends Tab ──

  Widget _buildFriendsTab(List<FriendData> friends) {
    if (friends.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.people_outline, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Нет друзей', style: TextStyle(color: Colors.grey, fontSize: 18)),
            SizedBox(height: 8),
            Text('Используйте вкладку «Поиск»',
                style: TextStyle(color: Color(0xFF8b949e))),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(multiplayerProvider.notifier).loadFriends(),
      child: ListView.builder(
        itemCount: friends.length,
        itemBuilder: (ctx, i) {
          final f = friends[i];
          return Card(
            color: const Color(0xFF16213e),
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: ListTile(
              leading: const CircleAvatar(
                backgroundColor: Color(0xFFc9a96e),
                child: Icon(Icons.person, color: Color(0xFF1a1a2e)),
              ),
              title: Text('@${f.username}',
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.group_add, color: Color(0xFFc9a96e)),
                    tooltip: 'Пригласить в партию',
                    onPressed: () => _inviteFriend(f.userId, f.username),
                  ),
                  IconButton(
                    icon: const Icon(Icons.person_remove, color: Colors.redAccent),
                    tooltip: 'Удалить',
                    onPressed: () async {
                      final confirm = await showDialog<bool>(
                        context: context,
                        builder: (ctx) => AlertDialog(
                          title: const Text('Удалить друга?'),
                          content: Text('Вы уверены, что хотите удалить @${f.username}?'),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(ctx, false),
                              child: const Text('Отмена'),
                            ),
                            TextButton(
                              onPressed: () => Navigator.pop(ctx, true),
                              child: const Text('Удалить',
                                  style: TextStyle(color: Colors.red)),
                            ),
                          ],
                        ),
                      );
                      if (confirm == true && mounted) {
                        await ref
                            .read(multiplayerProvider.notifier)
                            .removeFriend(f.userId);
                        ref.read(multiplayerProvider.notifier).loadFriends();
                      }
                    },
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ── Pending Tab ──

  Widget _buildPendingTab(List<FriendData> pending) {
    if (pending.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.mail_outline, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Нет входящих заявок',
                style: TextStyle(color: Colors.grey, fontSize: 18)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(multiplayerProvider.notifier).loadFriends(),
      child: ListView.builder(
        itemCount: pending.length,
        itemBuilder: (ctx, i) {
          final req = pending[i];
          return Card(
            color: const Color(0xFF16213e),
            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: ListTile(
              leading: const CircleAvatar(
                backgroundColor: Colors.orange,
                child: Icon(Icons.person_add, color: Color(0xFF1a1a2e)),
              ),
              title: Text('@${req.username}',
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
              subtitle: const Text('Хочет добавить вас в друзья',
                  style: TextStyle(color: Color(0xFF8b949e))),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    icon: const Icon(Icons.check_circle, color: Colors.green),
                    tooltip: 'Принять',
                    onPressed: () async {
                      await ref
                          .read(multiplayerProvider.notifier)
                          .acceptFriend(req.requestId ?? 0);
                      ref.read(multiplayerProvider.notifier).loadFriends();
                    },
                  ),
                  IconButton(
                    icon: const Icon(Icons.cancel, color: Colors.red),
                    tooltip: 'Отклонить',
                    onPressed: () async {
                      await ref
                          .read(multiplayerProvider.notifier)
                          .rejectFriend(req.requestId ?? 0);
                      ref.read(multiplayerProvider.notifier).loadFriends();
                    },
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  // ── Search Tab ──

  Widget _buildSearchTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtl,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Введите username...',
                    hintStyle: const TextStyle(color: Color(0xFF8b949e)),
                    filled: true,
                    fillColor: const Color(0xFF16213e),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide:
                          const BorderSide(color: Color(0xFFc9a96e)),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(
                          color: Color(0xFFc9a96e), width: 1),
                    ),
                    prefixIcon: const Icon(Icons.search,
                        color: Color(0xFF8b949e)),
                  ),
                  onSubmitted: (_) => _doSearch(),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: _searching ? null : _doSearch,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFc9a96e),
                  foregroundColor: const Color(0xFF1a1a2e),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                ),
                child: _searching
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Найти'),
              ),
            ],
          ),
        ),
        if (_searchResults.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(
              'Найдено: ${_searchResults.length}',
              style: const TextStyle(color: Color(0xFF8b949e)),
            ),
          ),
        Expanded(
          child: _searchResults.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.search, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text('Введите username для поиска',
                          style:
                              TextStyle(color: Color(0xFF8b949e), fontSize: 16)),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _searchResults.length,
                  itemBuilder: (ctx, i) {
                    final user = _searchResults[i];
                    return Card(
                      color: const Color(0xFF16213e),
                      margin: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 4),
                      child: ListTile(
                        leading: const CircleAvatar(
                          backgroundColor: Colors.green,
                          child: Icon(Icons.person, color: Color(0xFF1a1a2e)),
                        ),
                        title: Text('@${user['username']}',
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold)),
                        trailing: ElevatedButton.icon(
                          icon: const Icon(Icons.person_add, size: 18),
                          label: const Text('Добавить'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFc9a96e),
                            foregroundColor: const Color(0xFF1a1a2e),
                          ),
                          onPressed: () => _sendRequest(user['username']),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
