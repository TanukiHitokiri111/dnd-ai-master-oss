import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/api_service_provider.dart';
import '../theme/app_theme.dart';

/// Bottom sheet для смешанного наследия.
/// Все расы с can_mix=true — плоским списком с ползунками.
/// Универсальные (UNIVERSAL group) могут смешиваться с любыми.
/// Остальные — по совместимости из COMPAT_RULES (compatible_with).
/// Несовместимые расы визуально заблокированы.
class MixedHeritagePicker extends ConsumerStatefulWidget {
  const MixedHeritagePicker({super.key});

  @override
  ConsumerState<MixedHeritagePicker> createState() => _MixedHeritagePickerState();
}

class _MixedHeritagePickerState extends ConsumerState<MixedHeritagePicker> {
  bool _loadingConfig = true;
  bool _rolling = false;
  String? _configError;

  List<String> _allSpecies = [];
  Map<String, String> _groupMap = {}; // species → group
  Map<String, Set<String>> _compatMap = {}; // species → compatible species
  Map<String, int> _percentages = {};
  int _totalPercent = 0;
  Map<String, dynamic>? _result;

  static const _groupNames = {
    'AQUATIC': '🌊 Водные',
    'BEASTFOLK': '🐾 Зверолюды',
    'CONSTRUCT': '⚙️ Конструкты',
    'FEY': '🧚 Фейри',
    'GIANTKIN': '🪨 Гиганты',
    'GOBLINOID': '👹 Гоблиноиды',
    'HUMANOID': '🗡️ Гуманоиды',
    'MUTANT': '🧬 Мутанты',
    'ORC': '💀 Орки',
    'PLANETOUCHED': '✨ Планетарные',
    'PSIONIC': '🧠 Псионики',
    'REPTILIAN': '🦎 Рептилии',
    'UNDEAD_ADJACENT': '🕯️ Нежить',
    'UNIVERSAL': '🌈 Универсальные',
  };

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    try {
      final api = ref.read(chatApiServiceProvider);
      final cfg = await api.getMixedHeritageConfig();
      if (!mounted) return;

      final speciesList = (cfg['species'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      final names = <String>[];
      final groups = <String, String>{};
      final compatMap = <String, Set<String>>{};
      for (final s in speciesList) {
        if (s['can_mix'] != true) continue;
        final name = s['name'] as String?;
        final group = s['group'] as String?;
        if (name == null) continue;
        names.add(name);
        groups[name] = group ?? '';
        final compatRaw = s['compatible_with'] as List?;
        compatMap[name] = (compatRaw?.cast<String>() ?? <String>[]).toSet();
      }
      names.sort();

      setState(() {
        _allSpecies = names;
        _groupMap = groups;
        _compatMap = compatMap;
        _percentages = {for (final n in names) n: 0};
        _loadingConfig = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _configError = '$e';
        _loadingConfig = false;
      });
    }
  }

  // Species that currently have non-zero percentages (for display)
  Set<String> get _activeSpecies => _percentages.entries
      .where((e) => e.value > 0)
      .map((e) => e.key)
      .toSet();

  // Groups of active non-UNIVERSAL species (for display only)
  Set<String> get _activeGroups {
    final groups = <String>{};
    for (final name in _activeSpecies) {
      final g = _groupMap[name] ?? '';
      if (g != 'UNIVERSAL') groups.add(g);
    }
    return groups;
  }

  bool _isCompatible(String species) {
    final group = _groupMap[species] ?? '';
    // UNIVERSAL: compatible with all EXCEPT CONSTRUCT/UNDEAD_ADJACENT
    if (group == 'UNIVERSAL') {
      for (final active in _activeSpecies) {
        if (active == species) continue;
        final ag = _groupMap[active] ?? '';
        if (ag == 'CONSTRUCT' || ag == 'UNDEAD_ADJACENT') return false;
      }
      return true;
    }
    // If no active species — everything is available
    if (_activeSpecies.isEmpty) return true;
    // Species must be compatible with ALL active non-UNIVERSAL species
    for (final active in _activeSpecies) {
      if (active == species) continue;
      final activeGroup = _groupMap[active] ?? '';
      if (activeGroup == 'UNIVERSAL') continue;
      // Check both directions: active→species AND species→active (must match server)
      final compatOfActive = _compatMap[active] ?? <String>{};
      final compatOfSpecies = _compatMap[species] ?? <String>{};
      if (!compatOfActive.contains(species) || !compatOfSpecies.contains(active)) {
        return false;
      }
    }
    return true;
  }

  bool get _anySelected => _totalPercent > 0;

  void _setPercent(String species, int value) {
    if (_result != null) return;

    // Block incompatible races when groups are already active
    if (value > 0 && _anySelected && !_isCompatible(species)) return;

    final old = _percentages[species] ?? 0;
    final delta = value - old;
    final newTotal = _totalPercent + delta;
    if (newTotal > 100) return;

    setState(() {
      _percentages[species] = value;
      _totalPercent = newTotal;

      // When activating first race → zero out incompatible (stale) percentages
      if (old == 0 && value > 0) {
        for (final s in _allSpecies) {
          if (s != species && !_isCompatible(s) && (_percentages[s] ?? 0) > 0) {
            _totalPercent -= _percentages[s]!;
            _percentages[s] = 0;
          }
        }
      }
    });
  }

  Future<void> _roll() async {
    if (_totalPercent != 100) return;

    final active = _percentages.entries
        .where((e) => e.value > 0 && _isCompatible(e.key))
        .toList();
    if (active.length < 2) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Нужно минимум 2 расы с ненулевым процентом!')),
      );
      return;
    }

    setState(() => _rolling = true);
    try {
      final api = ref.read(chatApiServiceProvider);
      final result = await api.rollMixedHeritage(
        Map<String, int>.fromEntries(active),
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _rolling = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _rolling = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e')),
      );
    }
  }

  void _reset() {
    setState(() {
      _result = null;
      for (final s in _allSpecies) {
        _percentages[s] = 0;
      }
      _totalPercent = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.darkBrown,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.85),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Center(
            child: Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: AppTheme.gold.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 16),

          Text(
            _result != null ? '🎲 Наследие определено' : '🔄 Смешанное наследие',
            style: const TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            _result != null
                ? 'Доминантная раса: ${_result!['dominant_species']}'
                : _anySelected
                    ? 'Группа: ${_activeGroups.map((g) => _groupNames[g] ?? g).join(' + ')}'
                    : 'Распредели 100% между расами',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 14),
          ),

          // Legend line
          if (_anySelected && _result == null) ...[
            const SizedBox(height: 2),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.lock, size: 12, color: AppTheme.parchment.withValues(alpha: 0.3)),
              const SizedBox(width: 4),
              Text('Несовместимые расы заблокированы', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11)),
            ]),
          ],

          const SizedBox(height: 16),

          if (_loadingConfig)
            const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator(color: AppTheme.gold)))
          else if (_configError != null)
            Text('⚠️ $_configError', style: const TextStyle(color: Colors.red))
          else ...[
            if (_result == null) ...[
              LinearProgressIndicator(
                value: _totalPercent / 100,
                backgroundColor: AppTheme.gold.withValues(alpha: 0.1),
                valueColor: const AlwaysStoppedAnimation(AppTheme.gold),
              ),
              const SizedBox(height: 8),
              Text('$_totalPercent%', textAlign: TextAlign.center,
                style: TextStyle(color: _totalPercent == 100 ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.5), fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
            ],

            if (_result == null)
              Flexible(
                child: SingleChildScrollView(
                  child: Column(children: _allSpecies.map((s) => _buildSpeciesSlider(s)).toList()),
                ),
              )
            else ...[
              Flexible(child: SingleChildScrollView(child: _buildResult())),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _reset,
                    style: OutlinedButton.styleFrom(foregroundColor: AppTheme.gold, side: const BorderSide(color: AppTheme.gold)),
                    child: const Text('🔄 Заново'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: () => Navigator.pop(context, _result),
                    style: FilledButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
                    child: const Text('✅ Применить'),
                  ),
                ),
              ]),
            ],
          ],

          if (_result == null) ...[
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.pop(context, null),
                  style: OutlinedButton.styleFrom(foregroundColor: AppTheme.gold, side: const BorderSide(color: AppTheme.gold)),
                  child: const Text('Отмена'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: (_totalPercent == 100 && !_rolling) ? _roll : null,
                  style: FilledButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
                  child: _rolling
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                      : const Text('🎲 Бросить'),
                ),
              ),
            ]),
          ],
        ],
      ),
    );
  }

  Widget _buildSpeciesSlider(String species) {
    final value = _percentages[species] ?? 0;
    final compatible = _activeGroups.isEmpty || _isCompatible(species);
    final group = _groupMap[species] ?? '';
    final muted = !compatible && _anySelected;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Opacity(
        opacity: muted ? 0.35 : 1.0,
        child: Row(children: [
          SizedBox(
            width: 110,
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (muted)
                Icon(Icons.lock, size: 14, color: AppTheme.parchment.withValues(alpha: 0.3)),
              if (muted) const SizedBox(width: 4),
              Flexible(
                child: Text(
                  species,
                  style: TextStyle(
                    color: muted ? AppTheme.parchment.withValues(alpha: 0.3) : AppTheme.parchment,
                    fontSize: 14,
                    decoration: muted ? TextDecoration.lineThrough : null,
                  ),
                ),
              ),
            ]),
          ),
          Expanded(
            child: Slider(
              value: muted ? 0 : value.toDouble(),
              min: 0, max: 100,
              divisions: 100,
              activeColor: muted ? AppTheme.parchment.withValues(alpha: 0.1) : AppTheme.gold,
              inactiveColor: muted ? AppTheme.parchment.withValues(alpha: 0.05) : AppTheme.gold.withValues(alpha: 0.15),
              onChanged: muted ? null : (v) => _setPercent(species, v.round()),
            ),
          ),
          SizedBox(
            width: 36,
            child: Text(
              muted ? '—' : '$value%',
              textAlign: TextAlign.right,
              style: TextStyle(
                color: muted
                    ? AppTheme.parchment.withValues(alpha: 0.2)
                    : value > 0 ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.3),
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _buildResult() {
    final phys = (_result!['physical_traits'] as List?) ?? [];
    final magi = (_result!['magical_traits'] as List?) ?? [];
    final vis = (_result!['visual_traits'] as List?) ?? [];
    final langs = (_result!['languages'] as List?) ?? [];

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (vis.isNotEmpty) ...[
        const Text('👁 Внешность', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 4),
        ...vis.map((t) => Text('• ${t is Map ? t['desc'] ?? t['name'] ?? '' : t}',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 12))),
        const SizedBox(height: 12),
      ],
      if (phys.isNotEmpty) ...[
        const Text('💪 Физические черты', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 4),
        ...phys.map((t) => Text('• ${t is Map ? '${t['name']}: ${t['desc']}' : '???'}',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 12))),
        const SizedBox(height: 12),
      ],
      if (magi.isNotEmpty) ...[
        const Text('✨ Магические черты', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 4),
        ...magi.map((t) => Text('• ${t is Map ? '${t['name']}: ${t['desc']}' : '???'}',
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 12))),
        const SizedBox(height: 12),
      ],
      Text('🏃 Скорость: ${_result!['speed']} фт | 📏 Размер: ${_result!['size_category']}',
          style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.8), fontSize: 13)),
      Text('🗣 Языки: ${langs.join(', ')}',
          style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.8), fontSize: 13)),
    ]);
  }
}
