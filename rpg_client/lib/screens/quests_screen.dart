import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

class QuestsScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String characterName;

  const QuestsScreen({
    super.key,
    required this.characterId,
    required this.characterName,
  });

  @override
  ConsumerState<QuestsScreen> createState() => _QuestsScreenState();
}

class _QuestsScreenState extends ConsumerState<QuestsScreen> {
  List<Map<String, dynamic>> _quests = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      _quests = await ref.read(chatApiServiceProvider).listQuests(widget.characterId);
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'active': return Icons.flag;
      case 'completed': return Icons.check_circle;
      case 'failed': return Icons.cancel;
      default: return Icons.help;
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'active': return AppTheme.gold;
      case 'completed': return Colors.green;
      case 'failed': return Colors.red;
      default: return AppTheme.parchment;
    }
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'active': return 'В процессе';
      case 'completed': return 'Завершён';
      case 'failed': return 'Провален';
      default: return status;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: Text('📜 Квесты ${widget.characterName}'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
          : _error != null
              ? Center(child: Text('Ошибка: $_error', style: const TextStyle(color: Colors.red)))
              : _quests.isEmpty
                  ? const Center(
                      child: Text('Нет активных квестов', style: TextStyle(color: AppTheme.parchment, fontSize: 16)))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _quests.length,
                      itemBuilder: (ctx, i) => _buildQuestCard(_quests[i]),
                    ),
    );
  }

  Widget _buildQuestCard(Map<String, dynamic> q) {
    final status = q['status'] ?? 'active';
    final objectives = (q['objectives'] as List?) ?? [];
    final rewards = (q['rewards'] as Map?) ?? {};

    return Card(
      color: AppTheme.darkBrown,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _statusColor(status).withValues(alpha: 0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_statusIcon(status), color: _statusColor(status), size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(q['title'] ?? '???',
                    style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _statusColor(status).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(_statusLabel(status),
                    style: TextStyle(color: _statusColor(status), fontSize: 11)),
                ),
              ],
            ),
            if ((q['description'] as String?)?.isNotEmpty == true) ...[
              const SizedBox(height: 6),
              Text(q['description'], style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 12)),
            ],
            if ((q['source_npc'] as String?)?.isNotEmpty == true) ...[
              const SizedBox(height: 4),
              Text('От: ${q['source_npc']}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35), fontSize: 11)),
            ],
            if (objectives.isNotEmpty) ...[
              const SizedBox(height: 10),
              ...objectives.map((o) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Icon(
                      o['done'] == true ? Icons.check_box : Icons.check_box_outline_blank,
                      color: o['done'] == true ? Colors.green : AppTheme.parchment.withValues(alpha: 0.4),
                      size: 16,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        o['text'] ?? '',
                        style: TextStyle(
                          color: o['done'] == true
                              ? AppTheme.parchment.withValues(alpha: 0.4)
                              : AppTheme.parchment.withValues(alpha: 0.7),
                          fontSize: 12,
                          decoration: o['done'] == true ? TextDecoration.lineThrough : null,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
            ],
            if (rewards.isNotEmpty && status != 'failed') ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.card_giftcard, size: 14, color: AppTheme.gold),
                  const SizedBox(width: 4),
                  Text(
                    [
                      if (rewards['gold'] != null && rewards['gold'] > 0) '💰 ${rewards['gold']} зм',
                      if (rewards['xp'] != null && rewards['xp'] > 0) '⭐ ${rewards['xp']} XP',
                    ].join('  '),
                    style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.6), fontSize: 11),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
