// abilities_screen.dart — экран умений персонажа.
//
// Показывает:
// - Изученные умения (с текущим рангом и кнопкой «+ Ранг»)
// - Доступные умения (требуют 1 очко)
// - Умения «Далее» (затенены, открываются по цепочке)
// - Тап по карточке — детальный просмотр со всеми 5 рангами

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

/// Экран умений: распределение очков по рангам
class AbilitiesScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String classKey; // напр. "Солдат__nuclear_wasteland"
  final String characterName; // для AppBar

  const AbilitiesScreen({
    super.key,
    required this.characterId,
    required this.classKey,
    required this.characterName,
  });

  @override
  ConsumerState<AbilitiesScreen> createState() => _AbilitiesScreenState();
}

class _AbilitiesScreenState extends ConsumerState<AbilitiesScreen> {
  bool _loading = true;
  bool _busy = false;
  String? _error;
  int _points = 0;
  List<Map<String, dynamic>> _learned = [];
  List<Map<String, dynamic>> _available = [];
  List<Map<String, dynamic>> _next = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final r = await ref.read(chatApiServiceProvider).getAbilities(widget.characterId);
      if (!mounted) return;
      setState(() {
        _points = (r['points'] as int?) ?? 0;
        _learned = List<Map<String, dynamic>>.from(r['learned'] ?? []);
        _available = List<Map<String, dynamic>>.from(r['available'] ?? []);
        _next = List<Map<String, dynamic>>.from(r['next'] ?? []);
      });
    } on ChatApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _allocate(String key, int ranks) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(chatApiServiceProvider).allocateAbilities(
        widget.characterId,
        widget.classKey,
        [{'ability_key': key, 'ranks': ranks}],
      );
      if (!mounted) return;
      setState(() {
        _points = (r['points'] as int?) ?? 0;
        _learned = List<Map<String, dynamic>>.from(r['learned'] ?? []);
        _available = List<Map<String, dynamic>>.from(r['available'] ?? []);
        _next = List<Map<String, dynamic>>.from(r['next'] ?? []);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('✅ Готово'), backgroundColor: AppTheme.gold),
      );
    } on ChatApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка: ${e.message}'), backgroundColor: AppTheme.bloodRed),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка: $e'), backgroundColor: AppTheme.bloodRed),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _sectionTitle(String title, IconData icon) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 8, 4, 8),
      child: Row(
        children: [
          Icon(icon, color: AppTheme.gold, size: 18),
          const SizedBox(width: 6),
          Text(title, style: const TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _card({required Widget child, bool dimmed = false, VoidCallback? onTap}) {
    return Opacity(
      opacity: dimmed ? 0.55 : 1.0,
      child: Card(
        color: Colors.black26,
        margin: const EdgeInsets.only(bottom: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3)),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Padding(padding: const EdgeInsets.all(12), child: child),
        ),
      ),
    );
  }

  Widget _badge(String text, {Color? color}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: (color ?? AppTheme.gold).withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(text, style: TextStyle(color: color ?? AppTheme.gold, fontSize: 11)),
    );
  }

  /// Текущее описание ранга из a['ranks'] с guard на границы списка
  String _rankDesc(Map a, int rank) {
    final ranks = a['ranks'];
    if (ranks is List && rank >= 1 && rank <= ranks.length) {
      final item = ranks[rank - 1];
      if (item is Map) return '${item['desc'] ?? ''}';
    }
    return '';
  }

  Widget _learnedCard(Map a) {
    final rank = (a['rank'] as int?) ?? 0;
    final key = '${a['key'] ?? ''}';
    final type = a['type'] == 'active' ? 'Активное' : 'Пассивное';
    final stat = '${a['stat'] ?? ''}'.toUpperCase();
    return _card(
      onTap: () => _showDetail(key),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text('${a['name'] ?? key}',
                  style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15)),
              ),
              _badge('Ранг $rank/5'),
              const SizedBox(width: 6),
              _badge(type, color: AppTheme.leather),
            ],
          ),
          if (stat.isNotEmpty && stat != 'NULL')
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(stat, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11)),
            ),
          const SizedBox(height: 6),
          Text(_rankDesc(a, rank),
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.8), fontSize: 13, height: 1.3)),
          const SizedBox(height: 6),
          if (rank < 5)
            TextButton(
              onPressed: _busy || _points < 1 ? null : () => _allocate(key, 1),
              child: const Text('+ Ранг', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold)),
            )
          else
            Text('Максимум', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35), fontSize: 12)),
        ],
      ),
    );
  }

  Widget _availableCard(Map a) {
    final key = '${a['key'] ?? ''}';
    return _card(
      onTap: () => _showDetail(key),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text('${a['name'] ?? key}',
                  style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15)),
              ),
              _badge('1 очко'),
            ],
          ),
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text('Ур. ${a['unlock_level'] ?? '?'}',
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11)),
          ),
          const SizedBox(height: 6),
          Text('${a['desc'] ?? ''}',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.8), fontSize: 13, height: 1.3)),
          const SizedBox(height: 6),
          ElevatedButton(
            onPressed: _busy || _points < 1 ? null : () => _allocate(key, 1),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.gold,
              foregroundColor: AppTheme.darkBrown,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            ),
            child: const Text('Открыть', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  /// Имена prerequisite-умений для затенённых карточек «Далее».
  /// prereq — список ключей; если пусто, показываем заглушку.
  String _prereqNames(List prereqKeys) {
    final all = [..._learned, ..._available, ..._next];
    final names = <String>[];
    for (final k in prereqKeys) {
      final match = all.where((x) => x['key'] == k).toList();
      names.add(match.isNotEmpty ? '${match.first['name'] ?? k}' : '$k');
    }
    return names.join(', ');
  }

  /// Детальный просмотр умения: полное описание + все 5 рангов.
  void _showDetail(String abilityKey) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkBrown,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      isScrollControlled: true,
      builder: (ctx) => FutureBuilder<Map<String, dynamic>>(
        future: ref.read(chatApiServiceProvider).getAbilityDetail(widget.characterId, abilityKey),
        builder: (ctx, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Padding(
              padding: EdgeInsets.all(32),
              child: Center(child: CircularProgressIndicator(color: AppTheme.gold)),
            );
          }
          if (snap.hasError) {
            return Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.cloud_off, color: Colors.red),
                const SizedBox(height: 8),
                Text('Ошибка: ${snap.error}', style: const TextStyle(color: Colors.red, fontSize: 13)),
                const SizedBox(height: 12),
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Закрыть')),
              ]),
            );
          }
          final d = snap.data!;
          final detailRank = (d['rank'] as int?) ?? 0;
          final desc = d['desc'] is Map
              ? '${(d['desc'] as Map)['text'] ?? d['desc']}'
              : '${d['desc'] ?? ''}';
          final ranks = d['ranks'] is List ? d['ranks'] as List : const <dynamic>[];
          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text('${d['name'] ?? abilityKey}',
                          style: const TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
                      ),
                      if (detailRank > 0) _badge('Ранг $detailRank/5'),
                    ],
                  ),
                  if (desc.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(desc, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.85), fontSize: 13, height: 1.4)),
                  ],
                  const SizedBox(height: 12),
                  Flexible(
                    child: SingleChildScrollView(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (var i = 0; i < ranks.length; i++)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Container(
                                width: double.infinity,
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: (i + 1) == detailRank
                                      ? AppTheme.gold.withValues(alpha: 0.15)
                                      : Colors.black26,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: (i + 1) == detailRank
                                        ? AppTheme.gold
                                        : AppTheme.gold.withValues(alpha: 0.15),
                                  ),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text('Ранг ${i + 1}',
                                      style: TextStyle(
                                        color: (i + 1) == detailRank ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.6),
                                        fontSize: 12, fontWeight: FontWeight.bold)),
                                    const SizedBox(height: 2),
                                    Text('${(ranks[i] is Map ? ranks[i]['desc'] : '') ?? ''}',
                                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.85), fontSize: 13, height: 1.3)),
                                  ],
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                  SizedBox(
                    width: double.infinity,
                    child: TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Закрыть'),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _nextCard(Map a) {
    final key = '${a['key'] ?? ''}';
    final prereq = a['prereq'] is List ? a['prereq'] as List : <dynamic>[];
    final prereqText = prereq.isNotEmpty ? 'Требует: ${_prereqNames(prereq)}' : 'Открывается по цепочке';
    return _card(
      dimmed: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${a['name'] ?? key}',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(height: 4),
          Text(prereqText,
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.45), fontSize: 12)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text('Умения · ${widget.characterName}'),
        backgroundColor: AppTheme.darkBrown,
        foregroundColor: AppTheme.gold,
        actions: [
          if (_busy)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 22, height: 22,
                child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.gold),
              ),
            )
          else
            IconButton(icon: const Icon(Icons.refresh, color: AppTheme.gold), onPressed: _load),
          Container(
            margin: const EdgeInsets.only(right: 12),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.gold.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3)),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('$_points', style: const TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
                Text('очков', style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.6), fontSize: 9)),
              ],
            ),
          ),
        ],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
        : _error != null
          ? Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.cloud_off, size: 56, color: Colors.red),
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 14)),
                const SizedBox(height: 12),
                ElevatedButton(
                  onPressed: _load,
                  style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
                  child: const Text('Повторить'),
                ),
              ]),
            )
          : RefreshIndicator(
              color: AppTheme.gold,
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _sectionTitle('Изучено', Icons.school),
                  if (_learned.isEmpty)
                    _card(child: Text('Пока ничего не изучено',
                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)))
                  else
                    ..._learned.map(_learnedCard),
                  _sectionTitle('Доступно', Icons.lock_open),
                  if (_available.isEmpty)
                    _card(child: Text(
                      _points == 0 ? 'Очков нет — получите при повышении уровня' : 'Всё доступное изучено',
                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)))
                  else
                    ..._available.map(_availableCard),
                  _sectionTitle('Далее', Icons.lock),
                  if (_next.isEmpty)
                    _card(child: Text('Пока ничего не запланировано',
                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)))
                  else
                    ..._next.map(_nextCard),
                  const SizedBox(height: 24),
                ],
              ),
            ),
    );
  }
}
