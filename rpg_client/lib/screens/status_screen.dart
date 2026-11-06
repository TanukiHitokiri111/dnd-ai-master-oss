import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

class StatusScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String characterName;
  const StatusScreen({super.key, required this.characterId, required this.characterName});

  @override
  ConsumerState<StatusScreen> createState() => _StatusScreenState();
}

class _StatusScreenState extends ConsumerState<StatusScreen> with SingleTickerProviderStateMixin {
  StatusData? _status;
  bool _loading = true;
  String? _error;
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      _status = await ref.read(chatApiServiceProvider).getStatus(widget.characterId);
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  String _modStr(int v) => v >= 0 ? '+$v' : '$v';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: Text('📊 ${widget.characterName}'),
        bottom: TabBar(
          controller: _tabCtrl,
          labelColor: AppTheme.gold,
          unselectedLabelColor: AppTheme.parchment.withValues(alpha: 0.4),
          indicatorColor: AppTheme.gold,
          tabs: const [
            Tab(text: 'Статы'),
            Tab(text: 'Заклинания'),
            Tab(text: 'Навыки'),
          ],
        ),
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
        : _error != null
          ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.cloud_off, size: 48, color: Colors.red),
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 14), textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Повторить'),
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
              ),
            ]))
          : _status == null
            ? const Center(child: Text('Ошибка загрузки', style: TextStyle(color: AppTheme.parchment)))
          : TabBarView(
              controller: _tabCtrl,
              children: [_buildStatsTab(), _buildSpellsTab(), _buildSkillsTab()],
            ),
    );
  }

  // ─── TAB 1: Stats ───
  Widget _buildStatsTab() {
    final c = _status!.character;
    final saves = _status!.saves;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Header
        Card(
          color: AppTheme.gold.withValues(alpha: 0.1),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2))),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              Row(children: [
                CircleAvatar(backgroundColor: AppTheme.gold, radius: 22, child: Text('${c.level}', style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 18))),
                const SizedBox(width: 12),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(c.name, style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold)),
                  Text('${c.race} ${c.className}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6))),
                ]),
              ]),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  _statChip('❤️', '${c.hpCurrent}/${c.hpMax} HP'),
                  _statChip('🛡️', 'AC ${c.ac}'),
                  _statChip('⚡', '${c.speed} ft'),
                  _statChip('⭐', 'БМ ${_modStr(_status!.profBonus)}'),
                  _statChip('💰', '${c.gold} ЗМ'),
                ],
              ),
              if (_status!.castingAbility.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('🎯 Атака закл: ${_modStr(_status!.spellAttack)} | Сл: ${_status!.spellDc} (${_status!.castingAbility})',
                  style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.6), fontSize: 13)),
              ],
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // Stats
        const Text('Характеристики', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...['str', 'dex', 'con', 'int', 'wis', 'cha'].map((key) {
          final labels = {'str': 'СИЛ 💪', 'dex': 'ЛОВ 🤸', 'con': 'ТЕЛ 🛡️', 'int': 'ИНТ 🧠', 'wis': 'МУД 🦉', 'cha': 'ХАР 👑'};
          final val = c.stats[key] ?? 10;
          final mod = _modStr((val - 10) ~/ 2);
          final save = saves[key] ?? 0;
          return Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(color: AppTheme.gold.withValues(alpha: 0.05), borderRadius: BorderRadius.circular(10)),
            child: Row(children: [
              SizedBox(width: 90, child: Text(labels[key]!, style: const TextStyle(color: AppTheme.parchment, fontSize: 13))),
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(color: AppTheme.gold.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(8)),
                child: Center(child: Text('$val', style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15))),
              ),
              const SizedBox(width: 8),
              Text(mod, style: TextStyle(color: val >= 14 ? Colors.green : (val <= 9 ? Colors.red : Colors.white), fontSize: 14, fontWeight: FontWeight.bold)),
              const SizedBox(width: 16),
              Text('Спас: ${_modStr(save)}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12)),
            ]),
          );
        }),

        const SizedBox(height: 16),
        // Features
        if (c.features.isNotEmpty) ...[
          const Text('Умения и черты', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ...c.features.map((f) => Card(
            color: AppTheme.gold.withValues(alpha: 0.05),
            margin: const EdgeInsets.only(bottom: 4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            child: ListTile(
              leading: const Icon(Icons.auto_awesome, color: AppTheme.gold, size: 18),
              title: Text(f['name'] ?? '', style: const TextStyle(color: AppTheme.parchment, fontSize: 13)),
              subtitle: f['desc'] != null ? Text(f['desc'], maxLines: 3, overflow: TextOverflow.ellipsis, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 11)) : null,
              onTap: () => _showFeatureDetail(f),
              dense: true,
            ),
          )),
          const SizedBox(height: 8),
        ],

        // Backstory
        if (c.backstory.isNotEmpty) ...[
          const Text('Предыстория', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppTheme.gold.withValues(alpha: 0.03), borderRadius: BorderRadius.circular(10), border: Border.all(color: AppTheme.gold.withValues(alpha: 0.1))),
            child: Text(c.backstory, style: const TextStyle(color: AppTheme.parchment, height: 1.5)),
          ),
        ],

        // Languages
        const SizedBox(height: 16),
        const Text('🗣️ Языки', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (c.languages.where((l) => l.isNotEmpty).isEmpty)
          Text('Не выбраны', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 13))
        else
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: (c.languages.where((l) => l.isNotEmpty).toList()..sort()).map((l) => Chip(
              label: Text(l, style: const TextStyle(fontSize: 11)),
              backgroundColor: AppTheme.gold.withValues(alpha: 0.1),
              labelStyle: const TextStyle(color: AppTheme.gold),
              side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2)),
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            )).toList(),
          ),
        const SizedBox(height: 40),
      ]),
    );
  }

  Widget _statChip(String icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: AppTheme.gold.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
      child: Text('$icon $text', style: const TextStyle(color: AppTheme.gold, fontSize: 13)),
    );
  }

  // ─── TAB 2: Spells ───
  Widget _buildSpellsTab() {
    final spells = _status!.spells;
    final slots = _status!.spellSlots;

    if (spells.isEmpty) {
      return Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.auto_awesome, size: 48, color: AppTheme.gold.withValues(alpha: 0.3)),
          const SizedBox(height: 12),
          Text('Нет заклинаний', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 16)),
          const SizedBox(height: 4),
          Text('Спроси DM найти свиток!', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 12)),
        ]),
      );
    }

    // Group by level
    final grouped = <int, List<SpellData>>{};
    for (final s in spells) {
      grouped.putIfAbsent(s.spellLevel, () => []).add(s);
    }
    final levels = grouped.keys.toList()..sort();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Slots
        if (slots.isNotEmpty) ...[
          const Text('Ячейки заклинаний', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 4, children: slots.entries.map((e) {
            return Chip(
              label: Text('${e.key} ур: ${e.value}', style: const TextStyle(color: AppTheme.gold, fontSize: 12)),
              backgroundColor: AppTheme.gold.withValues(alpha: 0.1),
              side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2)),
            );
          }).toList()),
          const SizedBox(height: 16),
        ],
        // Spells by level
        ...levels.map((lvl) {
          final label = lvl == 0 ? 'Заговоры (бесконечно)' : '${lvl} уровень';
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.6), fontSize: 14, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            ...grouped[lvl]!.map((s) => _spellTile(s)),
            const SizedBox(height: 12),
          ]);
        }),
        const SizedBox(height: 40),
      ]),
    );
  }

  Widget _spellTile(SpellData s) {
    return Card(
      color: AppTheme.gold.withValues(alpha: 0.03),
      margin: const EdgeInsets.only(bottom: 2),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => _showSpellDetail(s),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(width: 6, height: 6, decoration: BoxDecoration(color: _schoolColor(s.school), shape: BoxShape.circle)),
                const SizedBox(width: 8),
                Expanded(child: Row(children: [
                  if (s.spellKey.startsWith('custom_'))
                    const Text('⭐ ', style: TextStyle(fontSize: 12)),
                  Expanded(child: Text(s.spellName, style: const TextStyle(color: AppTheme.parchment, fontSize: 13, fontWeight: FontWeight.w500))),
                ])),
              ]),
              const SizedBox(height: 2),
              Text('${s.school} · ${s.castingTime} · ${s.range}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.35), fontSize: 11)),
              if (s.flavor.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(s.flavor, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.4), fontSize: 10, fontStyle: FontStyle.italic)),
              ],
            ],
          ),
        ),
      ),
    );
  }

  void _showSpellDetail(SpellData s) {
    final descText = (s.desc != null && s.desc is Map && s.desc!['text'] != null)
        ? s.desc!['text'].toString()
        : '';
    final levelLabel = s.spellLevel == 0 ? 'Заговор' : '${s.spellLevel} уровень';
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
              Container(width: 10, height: 10, decoration: BoxDecoration(color: _schoolColor(s.school), shape: BoxShape.circle)),
              const SizedBox(width: 10),
              Expanded(child: Text(s.spellName, style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold))),
            ]),
            const SizedBox(height: 4),
            Text('$levelLabel · ${s.school}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)),
            if (s.flavor.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(s.flavor, style: const TextStyle(color: AppTheme.gold, fontSize: 13, fontStyle: FontStyle.italic, height: 1.5)),
            ],
            if (s.castingTime.isNotEmpty) ...[
              const SizedBox(height: 12),
              _spellInfo('Время', s.castingTime),
            ],
            if (s.range.isNotEmpty) _spellInfo('Дистанция', s.range),
            if (s.components.isNotEmpty) _spellInfo('Компоненты', s.components),
            if (s.duration.isNotEmpty) _spellInfo('Длительность', s.duration),
            if (descText.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(descText, style: const TextStyle(color: AppTheme.parchment, fontSize: 14, height: 1.6)),
            ],
            if (s.source.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Источник: ${s.source}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11)),
            ],
            if (s.notes.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('📝 ${s.notes}', style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 12, fontStyle: FontStyle.italic)),
            ],
            const SizedBox(height: 16),
            // Кнопка удаления
            Center(child: TextButton.icon(
              onPressed: () async {
                Navigator.pop(ctx);
                final confirm = await showDialog<bool>(
                  context: context,
                  builder: (dctx) => AlertDialog(
                    backgroundColor: AppTheme.darkBrown,
                    title: const Text('Забыть заклинание?', style: TextStyle(color: AppTheme.gold)),
                    content: Text('«${s.spellName}» будет удалено из книги заклинаний.', style: const TextStyle(color: AppTheme.parchment)),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(dctx, false), child: const Text('Отмена', style: TextStyle(color: AppTheme.gold))),
                      TextButton(onPressed: () => Navigator.pop(dctx, true), child: const Text('Забыть', style: TextStyle(color: Colors.red))),
                    ],
                  ),
                );
                if (confirm == true) {
                  await ref.read(chatApiServiceProvider).removeSpell(widget.characterId, s.id);
                  setState(() { _status = null; _load(); });
                }
              },
              icon: const Icon(Icons.delete_outline, color: Colors.red, size: 16),
              label: const Text('Забыть заклинание', style: TextStyle(color: Colors.red, fontSize: 12)),
              style: TextButton.styleFrom(foregroundColor: Colors.red.withValues(alpha: 0.5)),
            )),
          ]),
        ),
      ),
    );
  }

  Color _schoolColor(String school) {
    switch (school.toLowerCase()) {
      case 'воплощение': return Colors.red;
      case 'ограждение': return Colors.blue;
      case 'прорицание': return Colors.purple;
      case 'очарование': return Colors.pink;
      case 'иллюзия': return Colors.teal;
      case 'некромантия': return Colors.grey;
      case 'преобразование': return Colors.orange;
      default: return AppTheme.gold;
    }
  }

  Widget _spellInfo(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 100, child: Text('$label:', style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11))),
        Expanded(child: Text(value, style: const TextStyle(color: AppTheme.parchment, fontSize: 11))),
      ]),
    );
  }

  // ─── TAB 3: Skills ───
  Widget _buildSkillsTab() {
    final skills = _status!.skills;
    final c = _status!.character;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Навыки', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text('Бонус мастерства: ${_modStr(_status!.profBonus)}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12)),
        const SizedBox(height: 12),
        ...skills.entries.map((e) {
          final info = e.value as Map<String, dynamic>;
          final name = info['name'] ?? e.key;
          final bonus = (info['bonus'] as num?)?.toInt() ?? 0;
          final proficient = info['proficient'] == true;
          final stat = info['stat'] ?? '';
          final statName = info['stat_name'] ?? stat;
          final flavor = info['flavor'] ?? '';
          final statKey = stat.toString();
          final statIcons = {'str': '💪', 'dex': '🤸', 'con': '🛡️', 'int': '🧠', 'wis': '🦉', 'cha': '👑'};
          final statIcon = statIcons[statKey] ?? '🎯';

          return GestureDetector(
            onTap: () => _showSkillDetail(name.toString(), statName.toString(), statIcon, bonus, proficient, flavor),
            child: Container(
            margin: const EdgeInsets.only(bottom: 4),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: proficient ? AppTheme.gold.withValues(alpha: 0.08) : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: proficient ? AppTheme.gold.withValues(alpha: 0.15) : AppTheme.gold.withValues(alpha: 0.04)),
            ),
            child: Row(children: [
              if (proficient) ...[
                Container(width: 6, height: 6, decoration: const BoxDecoration(color: AppTheme.gold, shape: BoxShape.circle)),
                const SizedBox(width: 8),
              ] else
                const SizedBox(width: 14),
              Expanded(child: Text(name.toString(), style: TextStyle(color: proficient ? AppTheme.gold : AppTheme.parchment, fontSize: 13))),
              Text(statIcon, style: const TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text(statName.toString(), style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11)),
              const SizedBox(width: 12),
              Container(
                width: 28,
                height: 24,
                decoration: BoxDecoration(
                  color: proficient ? AppTheme.gold.withValues(alpha: 0.2) : AppTheme.gold.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Center(child: Text(_modStr(bonus), style: TextStyle(color: proficient ? AppTheme.gold : AppTheme.parchment, fontWeight: FontWeight.bold, fontSize: 12))),
              ),
            ]),
          ));
        }),

        const SizedBox(height: 24),
        const Text('🗣️ Языки', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        if (c.languages.where((l) => l.isNotEmpty).isEmpty)
          Text('Не выбраны', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 13))
        else
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: (c.languages.where((l) => l.isNotEmpty).toList()..sort()).map((l) => Chip(
              label: Text(l, style: const TextStyle(fontSize: 11)),
              backgroundColor: AppTheme.gold.withValues(alpha: 0.1),
              labelStyle: const TextStyle(color: AppTheme.gold),
              side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2)),
              visualDensity: VisualDensity.compact,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            )).toList(),
          ),
        const SizedBox(height: 40),
      ]),
    );
  }

  void _showSkillDetail(String name, String statName, String statIcon, int bonus, bool proficient, String flavor) {
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
              Text(statIcon, style: const TextStyle(fontSize: 24)),
              const SizedBox(width: 10),
              Expanded(child: Text(name, style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold))),
            ]),
            const SizedBox(height: 4),
            Text('$statName · ${_modStr(bonus)}${proficient ? " · Владение" : ""}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)),
            if (flavor.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(flavor, style: const TextStyle(color: AppTheme.gold, fontSize: 14, fontStyle: FontStyle.italic, height: 1.6)),
            ],
            const SizedBox(height: 16),
          ]),
        ),
      ),
    );
  }

  void _showFeatureDetail(Map<String, dynamic> f) {
    final name = f['name'] ?? '';
    final desc = f['desc'] ?? '';
    final source = f['source'] ?? '';
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
              const Icon(Icons.auto_awesome, color: AppTheme.gold, size: 24),
              const SizedBox(width: 10),
              Expanded(child: Text(name, style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold))),
            ]),
            if (source.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(source, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 12, fontStyle: FontStyle.italic)),
            ],
            if (desc.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(desc, style: const TextStyle(color: AppTheme.parchment, fontSize: 14, height: 1.6)),
            ],
            const SizedBox(height: 16),
          ]),
        ),
      ),
    );
  }
}
