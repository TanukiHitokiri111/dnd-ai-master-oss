import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

class InventoryScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String characterName;
  final int gold;
  final List<ItemData> preloadedItems;

  const InventoryScreen({
    super.key,
    required this.characterId,
    required this.characterName,
    required this.gold,
    this.preloadedItems = const [],
  });

  @override
  ConsumerState<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends ConsumerState<InventoryScreen> {
  List<ItemData> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.preloadedItems.isNotEmpty) {
      _items = widget.preloadedItems;
      _loading = false;
    } else {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      _items = await ref.read(chatApiServiceProvider).listItems(widget.characterId);
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _removeItem(ItemData item) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Удалить предмет?', style: TextStyle(color: AppTheme.gold)),
        content: Text('${item.itemName} будет удалён.', style: const TextStyle(color: AppTheme.parchment)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Удалить', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      final api = ref.read(chatApiServiceProvider);
      await api.removeItem(widget.characterId, item.id);
      await _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  IconData _itemIcon(String type) {
    switch (type) {
      case 'weapon': return Icons.gavel;
      case 'armor':  return Icons.shield;
      case 'focus':  return Icons.auto_awesome;
      case 'potion': return Icons.local_drink;
      case 'gear':   return Icons.backpack;
      case 'tool':   return Icons.build;
      case 'ammo':   return Icons.sports_martial_arts;
      default:       return Icons.category;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: Text('🎒 ${widget.characterName}'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text('💰 ${widget.gold} зм', style: const TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
          : _error != null
              ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.error_outline, size: 48, color: Colors.red.withValues(alpha: 0.6)),
                  const SizedBox(height: 12),
                  Text('Ошибка загрузки', style: TextStyle(color: Colors.red.withValues(alpha: 0.7), fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(_error!, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11)),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _load,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Повторить'),
                    style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
                  ),
                ]))
              : RefreshIndicator(
                  onRefresh: _load,
                  color: AppTheme.gold,
                  child: _buildItemList(),
                ),
    );
  }

  Widget _buildItemList() {
    if (_items.isEmpty) {
      return ListView(
        children: [
          SizedBox(height: MediaQuery.of(context).size.height * 0.3),
          Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.backpack, size: 64, color: AppTheme.gold.withValues(alpha: 0.3)),
              const SizedBox(height: 16),
              Text('Инвентарь пуст', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 18)),
              const SizedBox(height: 4),
              Text('Предметы появятся по ходу игры', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.25), fontSize: 13)),
            ]),
          ),
        ],
      );
    }

    // Group items by type
    final groups = <String, List<ItemData>>{};
    for (final item in _items) {
      groups.putIfAbsent(item.itemType, () => []).add(item);
    }

    final typeOrder = ['weapon', 'armor', 'shield', 'focus', 'potion', 'ammo', 'gear', 'tool'];
    final typeNames = {
      'weapon': '⚔️ Оружие',
      'armor': '🛡️ Броня',
      'shield': '🛡️ Щиты',
      'focus': '✨ Фокусы',
      'potion': '🧪 Зелья',
      'ammo': '🏹 Боеприпасы',
      'gear': '🎒 Снаряжение',
      'tool': '🔧 Инструменты',
    };

    final orderedGroups = <String>[];
    for (final t in typeOrder) {
      if (groups.containsKey(t)) orderedGroups.add(t);
    }
    for (final t in groups.keys) {
      if (!orderedGroups.contains(t)) orderedGroups.add(t);
    }

    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        for (final type in orderedGroups) ...[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4, left: 4),
            child: Row(children: [
              Icon(_itemIcon(type), color: AppTheme.gold, size: 18),
              const SizedBox(width: 6),
              Text(
                '${typeNames[type] ?? type} (${groups[type]!.length})',
                style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14),
              ),
            ]),
          ),
          ...groups[type]!.map((item) => Card(
            color: AppTheme.gold.withValues(alpha: 0.04),
            margin: const EdgeInsets.only(bottom: 4, left: 4, right: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            child: ListTile(
              leading: Icon(_itemIcon(item.itemType), color: AppTheme.parchment.withValues(alpha: 0.5), size: 24),
              title: Text(item.itemName, style: TextStyle(color: AppTheme.parchment, fontSize: 14, fontWeight: FontWeight.w500)),
              subtitle: item.flavor.isNotEmpty
                  ? Text(item.flavor,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.4), fontSize: 11, fontStyle: FontStyle.italic))
                  : Text('${item.itemSubtype} ×${item.qty}',
                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11)),
              trailing: IconButton(
                icon: const Icon(Icons.delete_outline, color: Colors.red, size: 18),
                onPressed: () => _removeItem(item),
              ),
              onTap: () => _showItemDetail(item),
              dense: true,
            ),
          )),
        ],
      ],
    );
  }

  void _showItemDetail(ItemData item) {
    if (!mounted) return;
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: AppTheme.darkBrown,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          border: Border(top: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3), width: 1)),
        ),
        padding: const EdgeInsets.all(20),
        child: SingleChildScrollView(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.3), borderRadius: BorderRadius.circular(2)))),
            const SizedBox(height: 16),
            Row(children: [
              Icon(_itemIcon(item.itemType), color: AppTheme.gold, size: 28),
              const SizedBox(width: 10),
              Expanded(child: Text(item.itemName, style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold))),
            ]),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 4, children: [
              _chip('${item.itemSubtype}'),
              _chip('×${item.qty}'),
              if (item.equipped) _chip('🎯 Экипирован', goldBg: true),
              if (item.attunement) _chip('🔮 Настроен', goldBg: true),
            ]),
            if (item.flavor.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(item.flavor, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 13, fontStyle: FontStyle.italic, height: 1.5)),
            ],
            if (item.slot != 'inventory' && item.slot.isNotEmpty) ...[
              const SizedBox(height: 12),
              Row(children: [
                Icon(Icons.accessibility_new, color: AppTheme.parchment.withValues(alpha: 0.4), size: 16),
                const SizedBox(width: 6),
                Text('Слот: ${item.slot}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 13)),
              ]),
            ],
            if (item.modifiers != null && item.modifiers!.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Модификаторы:', style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              ...item.modifiers!.entries.map((e) => Padding(
                padding: const EdgeInsets.only(left: 8, bottom: 2),
                child: Text('${e.key}: ${e.value}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 13)),
              )),
            ],
            if (item.notes.isNotEmpty) ...[
              const SizedBox(height: 12),
              Divider(color: AppTheme.gold.withValues(alpha: 0.25)),
              Text(item.notes, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12, height: 1.4)),
            ],
            const SizedBox(height: 16),
          ]),
        ),
      ),
    );
  }

  Widget _chip(String label, {bool goldBg = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: goldBg ? AppTheme.gold.withValues(alpha: 0.15) : AppTheme.gold.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppTheme.gold.withValues(alpha: goldBg ? 0.3 : 0.12)),
      ),
      child: Text(label, style: TextStyle(color: goldBg ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11)),
    );
  }
}
