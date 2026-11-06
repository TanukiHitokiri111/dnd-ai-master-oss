import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

class MapScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String characterName;

  const MapScreen({
    super.key,
    required this.characterId,
    required this.characterName,
  });

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  Map<String, dynamic>? _map;
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
      _map = await ref.read(chatApiServiceProvider).getCharacterMap(widget.characterId);
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: Text('🗺️ Карта мира — ${widget.characterName}'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
          : _error != null
              ? _buildError()
              : _buildMap(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.cloud_off, size: 56, color: Colors.red),
          const SizedBox(height: 12),
          Text('Не удалось загрузить карту', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7))),
          const SizedBox(height: 8),
          Text('$_error', textAlign: TextAlign.center, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12)),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            label: const Text('Повторить'),
          ),
        ]),
      ),
    );
  }

  Widget _buildMap() {
    final m = _map;
    if (m == null) return const SizedBox.shrink();
    final current = (m['current'] as Map?) ?? {};
    final discovered = (m['discovered'] as List?)?.cast<Map>() ?? [];
    final allCities = (m['all_cities'] as List?)?.cast<Map>() ?? [];
    final currentKey = (current['key'] ?? '') as String;
    final currentName = (current['name'] ?? '') as String;

    // Текущая локация открыта автоматически
    final knownKeys = <String>{};
    for (final d in discovered) {
      knownKeys.add((d['key'] ?? '') as String);
    }
    if (currentKey.isNotEmpty) knownKeys.add(currentKey);

    final known = <Map>[
      ...discovered,
      if (currentKey.isNotEmpty && !knownKeys.contains(currentKey))
        {
          'key': currentKey,
          'name': currentName,
          'desc': 'Текущая локация',
          'region': '—',
          'neighbors': <String>[],
        },
    ];

    return RefreshIndicator(
      onRefresh: _load,
      color: AppTheme.gold,
      backgroundColor: AppTheme.darkBrown,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(12),
        children: [
          // Текущая локация
          _currentCard(currentKey.isNotEmpty ? currentName : 'Неизвестно'),
          const SizedBox(height: 12),
          // Открытые города
          Text('📍 Открытые локации',
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 13, fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          if (known.isEmpty)
            _emptyCard('Карта ещё пуста. Путешествуйте по миру — новые города будут открываться.')
          else
            ...known.map(_cityCard),

          const SizedBox(height: 16),
          Text('🌍 Все города Фэйруна',
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 13, fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          ...allCities.map((c) {
            final key = (c['key'] ?? '') as String;
            final name = (c['name'] ?? '') as String;
            final open = knownKeys.contains(key);
            return ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(open ? Icons.location_on : Icons.lock, size: 18,
                  color: open ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.25)),
              title: Text(open ? name : '???', style: TextStyle(
                  color: open ? AppTheme.parchment : AppTheme.parchment.withValues(alpha: 0.3),
                  fontSize: 13)),
            );
          }),
        ],
      ),
    );
  }

  Widget _currentCard(String name) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.gold.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.4)),
      ),
      child: Row(children: [
        const Icon(Icons.flag, color: AppTheme.gold, size: 28),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Вы здесь', style: TextStyle(color: AppTheme.gold, fontSize: 11)),
            const SizedBox(height: 2),
            Text(name, style: const TextStyle(color: AppTheme.parchment, fontSize: 18, fontWeight: FontWeight.bold)),
          ]),
        ),
      ]),
    );
  }

  Widget _cityCard(Map d) {
    final key = (d['key'] ?? '') as String;
    final name = (d['name'] ?? '') as String;
    final desc = (d['desc'] ?? '') as String;
    final region = (d['region'] ?? '') as String;
    final neighbors = (d['neighbors'] as List?)?.cast<String>() ?? [];

    return Card(
      color: AppTheme.gold.withValues(alpha: 0.05),
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.15)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.location_city, color: AppTheme.gold, size: 18),
            const SizedBox(width: 6),
            Expanded(child: Text(name, style: const TextStyle(color: AppTheme.parchment, fontWeight: FontWeight.bold, fontSize: 15))),
            if (region.isNotEmpty)
              Text(region, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11)),
          ]),
          if (desc.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(desc, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 12)),
          ],
          if (neighbors.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text('Дороги ведут: ${neighbors.join(', ')}',
                style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 11)),
          ],
        ]),
      ),
    );
  }

  Widget _emptyCard(String text) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.gold.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.15)),
      ),
      child: Text(text, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
    );
  }
}
