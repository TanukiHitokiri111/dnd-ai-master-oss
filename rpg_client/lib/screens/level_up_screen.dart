/// level_up_screen.dart — повышение уровня и мультикласс.
///
/// Показывает:
/// - Текущие классы и уровни
/// - Выбор: повысить текущий класс или мультикласс
/// - Бросок хит-дайса
/// - ASI (+2/+1) на уровнях 4,8,12,16,19
/// - Полученные черты
/// - Новые слоты заклинаний

import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

/// Экран повышения уровня
class LevelUpScreen extends ConsumerStatefulWidget {
  final String characterId;
  final String characterName;
  final int currentLevel;
  final String currentClass;
  final Map<String, int> stats; // {"str":15, "dex":12, ...}
  final List<Map<String, dynamic>>? classes; // мультикласс

  const LevelUpScreen({
    super.key,
    required this.characterId,
    required this.characterName,
    required this.currentLevel,
    required this.currentClass,
    required this.stats,
    this.classes,
  });

  @override
  ConsumerState<LevelUpScreen> createState() => _LevelUpScreenState();
}

class _LevelUpScreenState extends ConsumerState<LevelUpScreen> {
  bool _loading = false;
  bool _showMulticlass = false;
  String? _selectedNewClass;
  int? _hpRoll;
  Map<String, int> _statIncrease = {};
  int _statPoints = 0;
  // Текущий итоговый уровень (растёт при повторных левелапах за один заход)
  late int _totalLevel;

  Map<String, dynamic>? _result;

  @override
  void initState() {
    super.initState();
    _totalLevel = widget.currentLevel;
    _fetchAvailableClasses();
  }

  // Доступные классы для мультикласса — тянутся с бэкенда с учётом мира
  // персонажа (бэкенд уже исключает взятые классы).
  List<String> _availableClasses = [];

  Future<void> _fetchAvailableClasses() async {
    try {
      final api = ref.read(chatApiServiceProvider);
      final classes = await api.getMulticlassClasses(widget.characterId);
      if (mounted) setState(() => _availableClasses = classes);
    } catch (_) {
      // Ошибка сети/авторизации — список останется пустым,
      // секция мультикласса просто не покажется.
    }
  }

  static const _statNames = {
    'str': '💪 Сила', 'dex': '🏃 Ловкость', 'con': '❤️ Телосложение',
    'int': '🧠 Интеллект', 'wis': '🦉 Мудрость', 'cha': '👑 Харизма',
  };

  static const _statIcons = {
    'str': '💪', 'dex': '🏃', 'con': '❤️',
    'int': '🧠', 'wis': '🦉', 'cha': '👑',
  };

  Set<String> get _currentClassNames {
    if (widget.classes == null || widget.classes!.isEmpty) return {widget.currentClass};
    return widget.classes!.map((c) => c['class_name'] as String).toSet();
  }

  List<String> get _availableMulticlasses =>
      _availableClasses.where((c) => !_currentClassNames.contains(c)).toList();

  // ASI уровни: 4, 8, 12, 16, 19 (стандарт), Воин +6,14, Плут +10
  // Проверяет TOTAL LEVEL — для одноклассовых персов совпадает с уровнем класса.
  // Для мультикласса ASI на уровне 1 нового класса не даётся (бэкенд проверит).
  bool get _isAsiLevel {
    final lvl = _newTotalLevel;
    return (lvl % 4 == 0 || lvl == 19) && lvl <= 19;
  }

  int get _newTotalLevel => _totalLevel + 1;

  int get _totalStatPoints => _statIncrease.values.fold(0, (a, b) => a + b);

  void _rollHp() {
    final rng = Random();
    final hitDie = _selectedNewClass != null ? _hitDieFor(_selectedNewClass!) : _hitDieFor(widget.currentClass);
    setState(() => _hpRoll = rng.nextInt(hitDie) + 1);
  }

  int _hitDieFor(String className) {
    return switch (className) {
      'Варвар' => 12,
      'Воин' || 'Паладин' || 'Следопыт' => 10,
      'Волшебник' || 'Чародей' => 6,
      _ => 8,
    };
  }

  void _addStat(String stat) {
    if (_totalStatPoints >= 2) return;
    setState(() {
      _statIncrease[stat] = (_statIncrease[stat] ?? 0) + 1;
    });
  }

  void _removeStat(String stat) {
    setState(() {
      final v = (_statIncrease[stat] ?? 0) - 1;
      if (v <= 0) {
        _statIncrease.remove(stat);
      } else {
        _statIncrease[stat] = v;
      }
    });
  }

  Future<void> _submit() async {
    setState(() => _loading = true);
    try {
      final api = ref.read(chatApiServiceProvider);
      final r = await api.levelUp(
        widget.characterId,
        newClass: _selectedNewClass,
        hpRoll: _hpRoll,
        statIncrease: _isAsiLevel && _statIncrease.isNotEmpty ? _statIncrease : null,
      );
      if (!mounted) return;
      // XP хватает ещё на уровень — сразу открываем форму следующего уровня
      if (r['more_levels'] == true) {
        setState(() {
          _totalLevel = (r['total_level'] as int?) ?? (_totalLevel + 1);
          _selectedNewClass = null;
          _showMulticlass = false;
          _hpRoll = null;
          _statIncrease = {};
          _result = null; // показываем форму снова
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('⬆️ Уровень повышен! XP хватает ещё на уровень — продолжай.'),
            backgroundColor: AppTheme.gold,
          ),
        );
        return;
      }
      setState(() => _result = r);
    } on ChatApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка: ${e.message}'), backgroundColor: AppTheme.bloodRed),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) return _buildResult();

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text('⬆️ ${widget.characterName} — Уровень ${_newTotalLevel}'),
        backgroundColor: AppTheme.darkBrown,
        foregroundColor: AppTheme.gold,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildClassSection(),
            const SizedBox(height: 16),
            _buildMulticlassSection(),
            const SizedBox(height: 16),
            _buildHpRollSection(),
            if (_isAsiLevel) ...[
              const SizedBox(height: 16),
              _buildAsiSection(),
            ],
            const SizedBox(height: 24),
            _buildSubmitButton(),
          ],
        ),
      ),
    );
  }

  Widget _buildClassSection() {
    return Card(
      color: AppTheme.darkBrown,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('🎯 Класс', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (widget.classes != null && widget.classes!.isNotEmpty)
              ...widget.classes!.map((c) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  '${c['class_name']} — уровень ${c['level']}',
                  style: TextStyle(color: AppTheme.parchment, fontSize: 14),
                ),
              ))
            else
              Text(
                '${widget.currentClass} — уровень ${widget.currentLevel}',
                style: TextStyle(color: AppTheme.parchment, fontSize: 14),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMulticlassSection() {
    final available = _availableMulticlasses;
    if (available.isEmpty) return const SizedBox.shrink();

    return Card(
      color: AppTheme.darkBrown,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('🔀 Мультикласс', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                const Spacer(),
                TextButton(
                  onPressed: () => setState(() {
                    _showMulticlass = !_showMulticlass;
                    if (!_showMulticlass) _selectedNewClass = null;
                  }),
                  child: Text(_showMulticlass ? 'Скрыть' : 'Выбрать другой класс',
                    style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.7), fontSize: 13),
                  ),
                ),
              ],
            ),
            if (_showMulticlass) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: available.map((cls) => ChoiceChip(
                  label: Text(cls),
                  selected: _selectedNewClass == cls,
                  onSelected: (v) => setState(() {
                    _selectedNewClass = v ? cls : null;
                    _hpRoll = null; // сбросить бросок HP
                  }),
                  selectedColor: AppTheme.gold.withValues(alpha: 0.2),
                  backgroundColor: AppTheme.leather.withValues(alpha: 0.3),
                  labelStyle: TextStyle(
                    color: _selectedNewClass == cls ? AppTheme.gold : AppTheme.parchment,
                    fontSize: 13,
                  ),
                  side: BorderSide(color: _selectedNewClass == cls ? AppTheme.gold : AppTheme.leather.withValues(alpha: 0.3)),
                )).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHpRollSection() {
    final className = _selectedNewClass ?? widget.currentClass;
    final hitDie = _hitDieFor(className);

    return Card(
      color: AppTheme.darkBrown,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('❤️ Хит-дайс: d$hitDie', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (_hpRoll == null)
              Text('Нажмите «Бросить» или оставьте пустым для среднего значения (${(hitDie ~/ 2) + 1})',
                style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 13))
            else
              Text('🎲 Выпало: $_hpRoll HP', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _rollHp,
              icon: const Text('🎲', style: TextStyle(fontSize: 20)),
              label: const Text('Бросить'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.gold,
                side: const BorderSide(color: AppTheme.gold),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAsiSection() {
    return Card(
      color: AppTheme.darkBrown,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('⭐ Увеличение характеристик', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.gold.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('${2 - _totalStatPoints} очк.',
                    style: TextStyle(color: AppTheme.gold, fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text('Распределите +2 очка (+1 к двум разным или +2 к одной). Максимум 20.',
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12)),
            const SizedBox(height: 12),
            ...widget.stats.entries.map((e) {
              final stat = e.key;
              final current = e.value;
              final bonus = _statIncrease[stat] ?? 0;
              final newVal = current + bonus;

              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 140,
                      child: Text('${_statNames[stat] ?? stat}: $current',
                        style: TextStyle(color: AppTheme.parchment, fontSize: 14)),
                    ),
                    if (bonus > 0)
                      Text('→ $newVal',
                        style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
                    const Spacer(),
                    if (newVal < 20 && _totalStatPoints < 2)
                      IconButton(
                        onPressed: () => _addStat(stat),
                        icon: const Icon(Icons.add_circle_outline, color: AppTheme.gold, size: 24),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (bonus > 0)
                      IconButton(
                        onPressed: () => _removeStat(stat),
                        icon: const Icon(Icons.remove_circle_outline, color: AppTheme.leather, size: 24),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildSubmitButton() {
    final canSubmit = _totalStatPoints == 2 || !_isAsiLevel;
    return ElevatedButton(
      onPressed: (_loading || !canSubmit) ? null : _submit,
      style: ElevatedButton.styleFrom(
        backgroundColor: AppTheme.gold,
        foregroundColor: AppTheme.darkBrown,
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
      ),
      child: _loading
        ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.darkBrown))
        : Text('⬆️ Повысить до уровня $_newTotalLevel'),
    );
  }

  Widget _buildResult() {
    final r = _result!;
    final hpGained = r['hp_gained'] as int;
    final hpMax = r['hp_max_new'] as int;
    final features = (r['features_gained'] as List?) ?? [];
    final classes = (r['classes'] as List?) ?? [];
    final spellSlots = r['spell_slots'] as Map<String, dynamic>?;
    final statIncreases = r['stat_increases_applied'] as Map<String, dynamic>?;
    final profs = r['proficiencies_gained'] as Map<String, dynamic>?;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('🎉 Уровень повышен!'),
        backgroundColor: AppTheme.darkBrown,
        foregroundColor: AppTheme.gold,
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(true), // true = уровень изменён
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Классы
            Card(
              color: AppTheme.darkBrown,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('🎯 Классы (уровень ${r['total_level']})',
                      style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ...classes.map((c) => Text(
                      '${c['class_name']} ${c['level']} (d${c['hit_die']})',
                      style: TextStyle(color: AppTheme.parchment, fontSize: 15),
                    )),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // HP
            Card(
              color: AppTheme.darkBrown,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('❤️ Здоровье', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text('+$hpGained HP → всего $hpMax HP',
                      style: TextStyle(color: AppTheme.parchment, fontSize: 15)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // ASI
            if (statIncreases != null && statIncreases.isNotEmpty)
              Card(
                color: AppTheme.darkBrown,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('⭐ Характеристики повышены',
                        style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      ...statIncreases.entries.map((e) =>
                        Text('${_statIcons[e.key] ?? ''} ${e.key.toUpperCase()}: +${e.value}',
                          style: TextStyle(color: AppTheme.parchment, fontSize: 14))),
                    ],
                  ),
                ),
              ),
            if (statIncreases != null && statIncreases.isNotEmpty) const SizedBox(height: 12),

            // Features
            if (features.isNotEmpty)
              Card(
                color: AppTheme.darkBrown,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('📜 Новые способности',
                        style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      ...features.map((f) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('▸ ${f['name']}',
                              style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.w600)),
                            Text(f['desc'] ?? '',
                              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 12)),
                          ],
                        ),
                      )),
                    ],
                  ),
                ),
              ),
            if (features.isNotEmpty) const SizedBox(height: 12),

            // Spell slots
            if (spellSlots != null && spellSlots.isNotEmpty)
              Card(
                color: AppTheme.darkBrown,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('🔮 Ячейки заклинаний',
                        style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      ...spellSlots.entries.map((e) =>
                        Text('Круг ${e.key}: ${e.value} ячеек',
                          style: TextStyle(color: AppTheme.parchment, fontSize: 14))),
                    ],
                  ),
                ),
              ),
            if (spellSlots != null && spellSlots.isNotEmpty) const SizedBox(height: 12),

            // Proficiencies
            if (profs != null) ...[
              if ((profs['armor'] as List?)?.isNotEmpty == true ||
                  (profs['weapons'] as List?)?.isNotEmpty == true ||
                  (profs['skills_count'] ?? 0) > 0)
                Card(
                  color: AppTheme.darkBrown,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('🛡️ Новые владения',
                          style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 4),
                        if ((profs['armor'] as List?)?.isNotEmpty == true)
                          Text('Броня: ${(profs['armor'] as List).join(', ')}',
                            style: TextStyle(color: AppTheme.parchment, fontSize: 13)),
                        if ((profs['weapons'] as List?)?.isNotEmpty == true)
                          Text('Оружие: ${(profs['weapons'] as List).join(', ')}',
                            style: TextStyle(color: AppTheme.parchment, fontSize: 13)),
                        if ((profs['skills_count'] ?? 0) > 0)
                          Text('Навыков на выбор: ${profs['skills_count']}',
                            style: TextStyle(color: AppTheme.parchment, fontSize: 13)),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: 16),
            ],

            // Done
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(true),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.gold,
                foregroundColor: AppTheme.darkBrown,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              child: const Text('👌 Готово'),
            ),
          ],
        ),
      ),
    );
  }
}
