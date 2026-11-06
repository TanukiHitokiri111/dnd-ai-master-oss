import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/app_config.dart';
import '../services/chat_api_service.dart';
import '../providers/api_service_provider.dart';
import '../providers/theme_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/mixed_heritage_picker.dart';

// ─── Point Buy ───
const Map<int, int> _pointBuyCost = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9};
const int _totalPoints = 27;
const int _baseStat = 8;
const int _maxPreRacial = 15;
const _statOrder = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
const Map<String, String> _statNames = {
  'str': 'СИЛ', 'dex': 'ЛОВ', 'con': 'ТЕЛ', 'int': 'ИНТ', 'wis': 'МУД', 'cha': 'ХАР',
};

// ─── Skill catalog ───
const Map<String, Map<String, String>> _skillCatalog = {
  'acrobatics':      {'name': 'Акробатика',          'stat': 'dex', 'desc': 'Балансирование, кувырки, сальто.'},
  'animal_handling': {'name': 'Уход за животными',   'stat': 'wis', 'desc': 'Успокоить животное, контролировать скакуна.'},
  'arcana':          {'name': 'Магия',                'stat': 'int', 'desc': 'Заклинания, магические предметы, планы бытия.'},
  'athletics':       {'name': 'Атлетика',             'stat': 'str', 'desc': 'Лазание, плавание, прыжки, борьба.'},
  'deception':       {'name': 'Обман',                'stat': 'cha', 'desc': 'Убедительная ложь, блеф, маскировка правды.'},
  'history':         {'name': 'История',              'stat': 'int', 'desc': 'События, войны, цивилизации, легенды.'},
  'insight':         {'name': 'Проницательность',    'stat': 'wis', 'desc': 'Чтение языка тела, определение лжи.'},
  'intimidation':    {'name': 'Запугивание',         'stat': 'cha', 'desc': 'Угрозы, психологическое давление.'},
  'investigation':   {'name': 'Расследование',       'stat': 'int', 'desc': 'Поиск улик, логические выводы, разгадка загадок.'},
  'medicine':        {'name': 'Медицина',             'stat': 'wis', 'desc': 'Диагностика, стабилизация умирающего.'},
  'nature':          {'name': 'Природа',              'stat': 'int', 'desc': 'Растения, животные, погода, география.'},
  'perception':      {'name': 'Восприятие',          'stat': 'wis', 'desc': 'Заметить врага, услышать шёпот, найти дверь.'},
  'performance':     {'name': 'Выступление',         'stat': 'cha', 'desc': 'Музыка, танец, актёрская игра, поэзия.'},
  'persuasion':      {'name': 'Убеждение',           'stat': 'cha', 'desc': 'Дипломатия, переговоры, тактичное влияние.'},
  'religion':        {'name': 'Религия',             'stat': 'int', 'desc': 'Божества, культы, ритуалы, святые символы.'},
  'sleight_of_hand': {'name': 'Ловкость рук',        'stat': 'dex', 'desc': 'Карманные кражи, фокусы, незаметные движения.'},
  'stealth':         {'name': 'Скрытность',          'stat': 'dex', 'desc': 'Бесшумное передвижение, маскировка в тенях.'},
  'survival':        {'name': 'Выживание',           'stat': 'wis', 'desc': 'Ориентирование, охота, выслеживание.'},
};
const Map<String, String> _statIcons = {'str': '💪', 'dex': '🤸', 'con': '🛡️', 'int': '🧠', 'wis': '🦉', 'cha': '👑'};

// ─── Languages ───
const List<String> _standardLanguages = ['Общий', 'Дварфийский', 'Эльфийский', 'Полуросличий', 'Гномий', 'Драконий', 'Великаний', 'Гоблинский', 'Орочий'];
const List<String> _exoticLanguages = ['Бездны', 'Небесный', 'Глубинная речь', 'Инфернальный', 'Первичный', 'Сильван', 'Подземный'];

// ─── Enums ───
enum CreateMode { quick, full }

class CharacterMasterScreen extends ConsumerStatefulWidget {
  final CreateMode mode;
  const CharacterMasterScreen({super.key, this.mode = CreateMode.full});
  @override
  ConsumerState<CharacterMasterScreen> createState() => _CharacterMasterScreenState();
}

class _CharacterMasterScreenState extends ConsumerState<CharacterMasterScreen> {
  // Data
  List<SrdRace> _races = [];
  List<SrdClass> _classes = [];
  Map<String, SubclassData> _subclasses = {};
  String? _dataError;

  // Step 0: World (выбор мира — первый шаг, до расы)
  static const Set<String> _excludedWorlds = {'primordial_chaos', 'astral_plane', 'elysium', 'absolute_order'};
  List<Map<String, dynamic>> _worlds = [];
  String? _selectedWorld;
  bool _loadingWorlds = true;
  bool _loadingWorldData = false;
  Map<String, dynamic> _worldContent = {};  // {descriptions: {}, rules: {}}

  // Step 1: Race
  String? _selectedRace;
  String? _selectedSubrace;
  Map<String, int> _activeStatBonuses = {};
  // Mixed race
  Map<String, dynamic>? _mixedHeritageResult;


  // Step 2: Class
  String? _selectedClass;
  String? _selectedSubclass;

  // Step 2: Stats
  final Map<String, int> _baseStats = {for (var s in _statOrder) s: 8};

  // Step 3: Skills
  List<String> _classSkills = [];
  int _skillsToPick = 2;
  final Set<String> _chosenSkills = {};
  final Set<String> _chosenLanguages = {};
  final _langCtrl = TextEditingController();

  // Step 4: Spells (casters only)
  bool _isCaster = false;
  List<SrdSpellData> _availableSpells = [];
  final Set<String> _chosenSpells = {};
  Map<String, dynamic> _spellSlots = {};
  int _maxCantrips = 3;
  int _maxLevel1 = 2;
  String _castingAbility = '';

  // Step 5: Name
  final _nameCtrl = TextEditingController();

  // Step: Background
  List<SrdBackground> _backgrounds = [];
  String? _selectedBg;
  final _backstoryCtrl = TextEditingController();

  // World-specific data (загружается при выборе мира)
  Map<String, List<dynamic>> _worldEquipment = {};  // предметы мира (raw items per world cache)
  Map<String, dynamic> _worldMap = {};  // карта мира: {regions, capital, notable_locations...}
  List<dynamic> _worldLanguages = [];  // языки мира: [{name, races, script, description}]
  Map<String, List<dynamic>> _worldBackgrounds = {};  // предыстории по расам: {раса: [{name, description...}]}
  List<dynamic> _worldSkills = [];  // уникальные навыки мира: [{key, name, stat, desc}]

  // UI state
  int _currentStep = 0;
  bool _saving = false;
  int _level = 1;

  @override
  void initState() {
    super.initState();
    _loadWorlds();
  }

  /// Шаг 0: загрузка списка миров + контента (getRaces/getClasses здесь НЕ вызываются).
  Future<void> _loadWorlds() async {
    try {
      final api = ref.read(chatApiServiceProvider);
      final results = await Future.wait([api.getWorlds(), api.getWorldContent()]);
      final worlds = results[0] as List<dynamic>;
      final content = results[1] as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _worlds = worlds.where((w) => !_excludedWorlds.contains(w['key'])).cast<Map<String, dynamic>>().toList();
        _worldContent = content;
        _loadingWorlds = false;
      });
    } catch (e) {
      if (mounted) setState(() { _loadingWorlds = false; _dataError = e.toString(); });
    }
  }

  /// Выбор мира: загрузить расы/классы/сабклассы/фоны мира, сбросить выбор, сменить тему.
  Future<void> _onWorldSelected(String worldKey) async {
    if (_loadingWorldData) return;
    setState(() => _loadingWorldData = true);
    try {
      final api = ref.read(chatApiServiceProvider);
      final w = await api.getWorldData(worldKey);
      if (!mounted) return;

      // Парсинг рас мира (SrdRace.fromJson принимает Map)
      final races = ((w['races'] as List?) ?? [])
          .whereType<Map<String, dynamic>>()
          .map((j) => SrdRace.fromJson(j))
          .toList();

      // Классы мира
      final classes = ((w['classes'] as List?) ?? [])
          .whereType<Map<String, dynamic>>()
          .map((j) => SrdClass.fromJson(j))
          .toList();

      // Сабклассы мира: {класс: {label, flavor, options}}
      final subMap = <String, SubclassData>{};
      final rawSubs = w['subclasses'];
      if (rawSubs is Map) {
        rawSubs.forEach((k, v) {
          if (v is Map<String, dynamic>) subMap[k.toString()] = SubclassData.fromJson(v);
        });
      }

      // Фоны мира (skills приходит строкой — SrdBackground.fromJson распарсит)
      final backgrounds = ((w['backgrounds'] as List?) ?? [])
          .whereType<Map<String, dynamic>>()
          .map((j) => SrdBackground.fromJson(j))
          .toList();

      // World-specific данные: параллельная загрузка (equipment, map, languages, backgrounds, skills)
      List<dynamic> equip = [], langs = [], wskills = [];
      Map<String, dynamic> wmap = {};
      Map<String, dynamic> wbgs = {};
      try {
        final extra = await Future.wait([
          api.getWorldEquipment(worldKey),   // 0: List items
          api.getWorldMap(worldKey),         // 1: Map regions/capital
          api.getWorldLanguages(worldKey),   // 2: List languages
          api.getWorldBackgrounds(worldKey), // 3: Map race → backgrounds
          api.getWorldSkills(worldKey),      // 4: List world skills
        ]);
        equip = extra[0] as List<dynamic>;
        wmap = extra[1] as Map<String, dynamic>;
        langs = extra[2] as List<dynamic>;
        wbgs = extra[3] as Map<String, dynamic>;
        wskills = extra[4] as List<dynamic>;
      } catch (_) {
        // Некритично: если world-данные не загрузились — шаги работают на стандартных SRD-данных
      }

      if (!mounted) return;
      setState(() {
        _selectedWorld = worldKey;
        _races = races;
        _classes = classes;
        _subclasses = subMap;
        _backgrounds = backgrounds;
        _selectedBg = backgrounds.isNotEmpty ? backgrounds.first.name : null;
        _worldEquipment = {worldKey: equip};
        _worldMap = wmap;
        _worldLanguages = langs;
        _worldBackgrounds = wbgs.cast<String, List<dynamic>>();
        _worldSkills = wskills;
        _resetCharacterChoices();
        _loadingWorldData = false;
      });
      // Глобальная смена темы приложения под выбранный мир
      ref.read(themeProvider.notifier).setWorldTheme(worldKey);
      // Перейти на шаг расы
      _goNext();
    } catch (e) {
      if (mounted) {
        setState(() => _loadingWorldData = false);
        _snack('Ошибка загрузки мира: $e');
      }
    }
  }

  /// Сброс выбора при смене мира (раса/класс/сабкласс/навыки/заклинания/статы).
  void _resetCharacterChoices() {
    _selectedRace = null;
    _selectedSubrace = null;
    _mixedHeritageResult = null;
    _selectedClass = null;
    _selectedSubclass = null;
    _activeStatBonuses = {};
    for (final s in _statOrder) {
      _baseStats[s] = _baseStat;
    }
    _chosenSkills.clear();
    _chosenLanguages.clear();
    _chosenSpells.clear();
    _isCaster = false;
  }

  @override
  void dispose() { _nameCtrl.dispose(); _langCtrl.dispose(); _backstoryCtrl.dispose(); super.dispose(); }

  // ─── Stat helpers ───
  int _pointsSpent() { int pts = 0; for (final s in _statOrder) pts += _pointBuyCost[_baseStats[s]!] ?? 0; return pts; }
  int _pointsRemaining() => _totalPoints - _pointsSpent();
  bool _canInc(String s) => _baseStats[s]! < _maxPreRacial && _pointsRemaining() >= (_pointBuyCost[_baseStats[s]! + 1] ?? 99) - (_pointBuyCost[_baseStats[s]] ?? 0);
  bool _canDec(String s) => _baseStats[s]! > _baseStat;
  int _finalStat(String stat) => _baseStats[stat]! + (_activeStatBonuses[stat] ?? 0);
  int _modifier(int v) => (v - 10) ~/ 2;
  String _modStr(int v) { final m = _modifier(v); return m >= 0 ? '+$m' : '$m'; }
  void _applyStandardArray() => setState(() {
    _baseStats['str'] = 15; _baseStats['dex'] = 14; _baseStats['con'] = 13;
    _baseStats['int'] = 12; _baseStats['wis'] = 10; _baseStats['cha'] = 8;
  });

  // ─── Race logic ───
  void _onRaceChanged(String rn) {
    if (rn == 'Смешанная') {
      _showMixedHeritagePicker();
      return;
    }
    final race = _races.firstWhere((r) => r.name == rn, orElse: () => _races.isNotEmpty ? _races[0] : SrdRace(name: '', description: '', traits: []));
    setState(() {
      _selectedRace = rn;
      _selectedSubrace = null;
      _mixedHeritageResult = null;
      _activeStatBonuses = Map<String, int>.from(race.statBonuses);
      // Мировые предыстории зависят от расы — сбросить выбор, если текущая недоступна
      final available = _availableBackgrounds;
      if (!available.any((b) => b.name == _selectedBg)) {
        _selectedBg = available.isNotEmpty ? available.first.name : null;
      }
      // Для Warhammer 40k — сбросить класс, если он не подходит новой фракции
      if (_selectedWorld == 'warhammer_40k' && _selectedClass != null) {
        final prefix = '$rn: ';
        if (!_selectedClass!.startsWith(prefix)) {
          _selectedClass = null;
          _selectedSubclass = null;
          _chosenSkills.clear();
        }
      }
      // Убрать из выбранных уникальные навыки мира, недоступные новой расе/классу
      if (_worldSkills.isNotEmpty && _chosenSkills.isNotEmpty) {
        final allowed = _worldSkillsForClass().map((s) => (s['key'] ?? s['name'] ?? '').toString()).toSet();
        final worldKeys = _worldSkills.whereType<Map<String, dynamic>>().map((s) => (s['key'] ?? s['name'] ?? '').toString()).toSet();
        _chosenSkills.removeWhere((k) => worldKeys.contains(k) && !allowed.contains(k));
      }
      // Пересчитать лимит навыков под новую пару раса×класс
      _applyWorldSkillsCap();
    });
  }

  Future<void> _showMixedHeritagePicker() async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const MixedHeritagePicker(),
    );
    if (!mounted) return;
    if (result != null) {
      setState(() {
        _selectedRace = 'Смешанная';
        _selectedSubrace = null;
        _mixedHeritageResult = result;
        _activeStatBonuses = {}; // бэкенд применит бонусы через heritage roller
        // Мировые предыстории зависят от расы — сбросить выбор, если текущая недоступна
        final available = _availableBackgrounds;
        if (!available.any((b) => b.name == _selectedBg)) {
          _selectedBg = available.isNotEmpty ? available.first.name : null;
        }
      });
      _goNext(); // сразу на класс
    }
  }

  void _onSubraceChanged(SubracePreview sr) => setState(() { _selectedSubrace = sr.key; _activeStatBonuses = Map<String, int>.from(sr.statBonuses); });

  void _snack(String msg) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty) { _snack('Введите имя'); return; }
    setState(() => _saving = true);
    try {
      final api = ref.read(chatApiServiceProvider);
      final draft = await api.createDraft(
        _nameCtrl.text.trim(), _selectedRace!, _selectedClass!, '', _selectedSubclass ?? '', _selectedSubrace ?? '',
        _mixedHeritageResult,
        _selectedWorld ?? '',
      );
      final charId = draft['id'] as String;
      await api.setStats(charId, {for (var s in _statOrder) s: _finalStat(s)}, _chosenSkills.toList(), _chosenLanguages.toList());
      if (_isCaster && _chosenSpells.isNotEmpty) {
        for (final sk in _chosenSpells) {
          try { await api.addSpell(charId, sk, source: 'creation'); } catch (_) {}
        }
      }
      await api.finalizeCharacter(charId, _backstoryCtrl.text.trim(), _selectedBg!);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => _saving = false);
      if (mounted) _snack('Ошибка: $e');
    }
  }

  // ─── BUILD ───
  @override
  Widget build(BuildContext context) {
    // Тема привязана к выбранному миру; сюда попадает и дефолт (мир ещё не выбран)
    final theme = ref.watch(themeProvider);
    final surface = theme.colorScheme.surface;
    if (_loadingWorlds) return Scaffold(backgroundColor: surface, body: const Center(child: CircularProgressIndicator()));
    if (_dataError != null) {
      return Scaffold(
        backgroundColor: surface,
        body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text('$_dataError', style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 12),
          ElevatedButton(onPressed: _loadWorlds, child: const Text('Повторить')),
        ])),
      );
    }
    return widget.mode == CreateMode.quick ? _quickMode() : _fullMode();
  }

  // ─── Quick mode (one scroll + floating save) ───
  Widget _quickMode() {
    final steps = <Widget>[
      _worldPicker(), const SizedBox(height: 16),
      if (_selectedWorld != null) ...[
        _racePicker(), const SizedBox(height: 16), _classPicker(), const SizedBox(height: 16),
        _statsBlock(), const SizedBox(height: 16), _skillsBlock(),
        if (_isCaster) ...[const SizedBox(height: 16), _spellsBlock()],
        const SizedBox(height: 16), _backgroundPicker(),
        const SizedBox(height: 16), _nameField(), const SizedBox(height: 80),
      ],
    ];
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(title: const Text('Быстрое создание')),
      body: SingleChildScrollView(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: steps)),
      floatingActionButton: FloatingActionButton.extended(onPressed: _saving ? null : _save, backgroundColor: AppTheme.gold, label: _saving ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.black)) : const Text('Создать', style: TextStyle(color: Colors.black))),
    );
  }

  // ─── Class logic ───
  void _onClassChanged(String cn) {
    final cls = _classes.firstWhere((c) => c.name == cn, orElse: () => _classes.isNotEmpty ? _classes[0] : SrdClass(name: '', description: '', hitDie: 8, proficiencies: {}, features: [], startingEquipment: {}));
    final sc = cls.proficiencies['skills_choices'];
    if (sc is Map) {
      _classSkills = (sc['from'] as List?)?.cast<String>() ?? [];
      _skillsToPick = sc['count'] as int? ?? 2;
    } else {
      _classSkills = []; _skillsToPick = 2;
    }
    setState(() { _selectedClass = cn; _selectedSubclass = null; _chosenSkills.clear(); });
    // Мир с уникальными навыками: у пары раса×класс их может быть меньше,
    // чем требует классовый skills_choices.count — не даём шагу застрять.
    _applyWorldSkillsCap();
  }

  /// Лимит выбираемых навыков: не больше, чем уникальных навыков мира
  /// доступно выбранной паре раса×класс (иначе шаг навыков не пройти).
  void _applyWorldSkillsCap() {
    if (_worldSkills.isEmpty) return;
    // База — классовый skills_choices.count (при смене расы восстанавливаем её)
    if (_selectedClass != null) {
      for (final c in _classes) {
        if (c.name == _selectedClass) {
          final sc = c.proficiencies['skills_choices'];
          if (sc is Map && sc['count'] is int) _skillsToPick = sc['count'] as int;
          break;
        }
      }
    }
    _skillsToPick = _skillsToPick.clamp(0, _worldSkillsForClass().length);
  }

  // ─── Spell helpers ───
  int _spellLevelForKey(String key) {
    for (final s in _availableSpells) { if (s.key == key) return s.level; }
    return 0;
  }

  // ─── Navigation (page-based wizard) ───
  int _step = 0;

  List<String> get _stepTags {
    final tags = <String>['world'];
    tags.add('race');
    tags.add('class');
    tags.add('stats');
    tags.add('skills');
    if (_isCaster) tags.add('spells');
    tags.add('background');
    tags.add('name');
    return tags;
  }

  String get _currentTag => _step < _stepTags.length ? _stepTags[_step] : 'name';
  bool get _isLastStep => _step == _stepTags.length - 1;

  String _pageLabel(String tag) {
    switch (tag) {
      case 'world': return 'Мир';
      case 'race': return _selectedWorld == 'warhammer_40k' ? 'Фракция' : 'Раса';
      case 'class': return 'Класс';
      case 'stats': return 'Характеристики';
      case 'skills': return 'Навыки и языки';
      case 'spells': return 'Заклинания';
      case 'background': return 'Предыстория';
      case 'name': return 'Имя';
      default: return '';
    }
  }

  bool _canProceed() {
    switch (_currentTag) {
      case 'world': return _selectedWorld != null;
      case 'race': return _selectedRace != null;
      case 'class': return _selectedClass != null;
      case 'stats': return _pointsSpent() == _totalPoints;
      case 'skills': return _chosenSkills.length >= _skillsToPick;
      case 'spells':
        final c = _chosenSpells.where((k) => _spellLevelForKey(k) == 0).length;
        final l1 = _chosenSpells.where((k) => _spellLevelForKey(k) > 0).length;
        return c >= _maxCantrips && l1 >= _maxLevel1;
      case 'background': return _selectedBg != null;
      case 'name': return _nameCtrl.text.trim().isNotEmpty;
      default: return false;
    }
  }

  void _goNext() {
    if (!_canProceed()) {
      _snack('Заполните текущий шаг');
      return;
    }
    if (_isLastStep) { _save(); return; }
    setState(() => _step++);
  }

  void _goBack() { if (_step > 0) setState(() => _step--); }

  Widget _pageFor(String tag) {
    switch (tag) {
      case 'world': return _worldPicker();
      case 'race': return _racePicker();
      case 'class': return _classPicker();
      case 'stats': return _statsBlock();
      case 'skills': return _skillsBlock();
      case 'spells': return _spellsBlock();
      case 'background': return _backgroundPicker();
      case 'name': return _nameField();
      default: return const SizedBox();
    }
  }

  // ─── Full mode (page-based wizard) ───
  Widget _fullMode() {
    final theme = Theme.of(context);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) return;
        // Возврат на предыдущий шаг; при выходе с шага мира — возвращаем дефолтную тему
        if (_step == 0) {
          ref.read(themeProvider.notifier).setWorldTheme(null);
          Navigator.of(context).pop();
        } else {
          _goBack();
        }
      },
      child: Stack(children: [
        Scaffold(
          backgroundColor: theme.colorScheme.surface,
          appBar: AppBar(
            title: Text('Создание персонажа — $_pageLabel($_currentTag)'),
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: _pageFor(_currentTag),
          ),
          bottomNavigationBar: _bottomBar(),
        ),
        if (_loadingWorldData)
          Positioned.fill(
            child: Container(
              color: Colors.black.withValues(alpha: 0.55),
              child: const Center(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 12),
                  Text('Пробуждаю мир...', style: TextStyle(fontSize: 14)),
                ]),
              ),
            ),
          ),
      ]),
    );
  }

  Widget _bottomBar() {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;
    final surface = theme.colorScheme.surface;
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: surface,
          border: Border(top: BorderSide(color: primary.withValues(alpha: 0.2))),
        ),
        child: Row(children: [
          if (_step > 0)
            Expanded(child: OutlinedButton(
              onPressed: _saving ? null : _goBack,
              style: OutlinedButton.styleFrom(
                foregroundColor: primary,
                side: BorderSide(color: primary),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: const Text('Назад'),
            )),
          if (_step > 0) const SizedBox(width: 12),
          Expanded(
            flex: _step > 0 ? 2 : 1,
            child: ElevatedButton(
              onPressed: _saving ? null : _goNext,
              style: ElevatedButton.styleFrom(
                backgroundColor: primary,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: _saving
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(color: Colors.black, strokeWidth: 2))
                : Text(_isLastStep ? 'Создать' : 'Далее',
                    style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
          ),
        ]),
      ),
    );
  }

  // ─────────────────────── WORLD PICKER (шаг 0) ───────────────────────
  static const Map<String, String> _techLevelIcons = {
    'divine': '✨', 'medieval': '🏰', 'magi-tech': '⚙️', 'steam': '🎩',
    'diesel': '🛢️', 'w40k_scifi': '💀', 'warp_scifi': '🌌', 'subluminal_scifi': '🚀',
    'postapoc': '☢️', 'scifi': '🤖', 'modern': '🏙️', 'cyberpunk': '🌐',
    'orbital': '🛰️', 'solar_system': '🪐',
  };

  static String _worldEmoji(Map<String, dynamic> w) =>
      _techLevelIcons[(w['tech_level'] ?? '').toString()] ?? '🌍';

  // ─── Хелперы локализации ───
  static const Map<String, String> _techLevelLabels = {
    'divine': 'Божественное',
    'medieval': 'Средневековье',
    'magi-tech': 'Маго-технологии',
    'steam': 'Пар',
    'diesel': 'Дизель',
    'w40k_scifi': 'Готическая фантастика',
    'warp_scifi': 'Варп-технологии',
    'subluminal_scifi': 'Досветовые полёты',
    'postapoc': 'Постапокалипсис',
    'scifi': 'Фантастика',
    'modern': 'Современность',
    'cyberpunk': 'Киберпанк',
    'orbital': 'Орбитальные технологии',
    'solar_system': 'Колониальные технологии',
  };

  static const Map<String, String> _genreLabels = {
    'weird': 'Сюрреализм',
    'fantasy': 'Фэнтези',
    'horror': 'Хоррор',
    'steam_punk': 'Стимпанк',
    'fantasy_scifi': 'Фэнтези-фантастика',
    'grimdark_warhammer': 'Гримдарк-фэнтези',
    'space_empires': 'Космические империи',
    'diesel_punk': 'Дизельпанк',
    'space_orbital': 'Космос (орбита)',
    'space_solar': 'Солнечная система',
    'space_colonial': 'Колониальный космос',
    'postapoc': 'Постапокалипсис',
    'scifi': 'Фантастика',
    'order': 'Абсолютный порядок',
  };

  static String _translateTechLevel(String en) => _techLevelLabels[en] ?? en;
  static String _translateGenre(String en) => _genreLabels[en] ?? en;

  static String _translateRuleKey(String key) {
    const rules = {
      'magic_multiplier': 'Множитель магии',
      'wild_magic_chance': 'Шанс дикой магии',
      'primordial_attention': 'Внимание Первозданных',
      'no_gravity': 'Нет гравитации',
      'time_unstable': 'Нестабильное время',
      'no_aging': 'Нет старения',
      'divine_attention_chance': 'Шанс внимания богов',
      'gods_active': 'Боги активны',
      'no_necromancy': 'Некромантия невозможна',
      'spell_scrolls_common': 'Распространённые свитки',
      'archmage_politics': 'Политика архимагов',
      'no_mundane_weapons_bonus': 'Нет бонуса простого оружия',
      'named_weapons_common': 'Именное оружие распространено',
      'fey_active': 'Фейри активны',
      'guild_politics': 'Политика гильдий',
      'healing_halved': 'Лечение вдвое слабее',
      'healing_magic_disabled': 'Магия лечения отключена',
      'death_saves_disadvantage': 'Спасброски от смерти с помехой',
      'firearms_available': 'Доступно огнестрельное оружие',
      'firearms_standard': 'Огнестрельное оружие стандартно',
      'steam_tech_standard': 'Паровые технологии стандартны',
      'alchemy_available': 'Алхимия доступна',
      'vacuum_hazard': 'Опасность вакуума',
      'microgravity_common': 'Частая микрогравитация',
      'oxygen_tracking': 'Отслеживание кислорода',
      'corporate_control': 'Власть корпораций',
      'psi_awakening': 'Пробуждение псионики',
      'magitech_hybrid': 'Гибрид магии и технологии',
      'diesel_tech_standard': 'Дизельные технологии стандартны',
      'war_rationing': 'Военные нормы',
      'escape_only_by_flow': 'Выход только через Поток',
      'dark_lords_active': 'Тёмные владыки активны',
      'magic_items_disabled': 'Магические предметы не работают',
      'no_srd_rules': 'Стандартные правила D&D не действуют',
      'survival_focus': 'Фокус на выживание',
      'radiation_hazard': 'Опасность радиации',
      'technology_disabled': 'Технологии не работают',
      'no_free_will': 'Нет свободы воли',
      'time_linear': 'Время строго линейно',
      'stat_remap': 'Переопределение характеристик',
      'cyberware_available': 'Киберимпланты доступны',
      'technology_standard': 'Технологии стандартны',
    };
    return rules[key] ?? key;
  }

  static String _translateRuleValue(String key, dynamic val) {
    if (val is bool) return val ? '✅ Да' : '❌ Нет';
    if (val is num) {
      if (key == 'magic_multiplier') return '×${val}x';
      if (key.contains('chance')) return '${(val * 100).toInt()}%';
      return val.toString();
    }
    return val.toString();
  }

  static String _tierLabel(dynamic tier) {
    final t = (tier as num?)?.toDouble() ?? 0.0;
    if (t >= 2.0) return 'Божественный';
    if (t >= 1.0) return 'Высокая магия';
    if (t >= 0.5) return 'Магия выше среднего';
    if (t >= 0.0) return 'Стандарт';
    if (t >= -1.0) return 'Низкая магия';
    if (t >= -2.0) return 'Без магии';
    return 'Мёртвый мир';
  }

  Widget _worldPicker() {
    if (_worlds.isEmpty) {
      return const Center(child: Text('Список миров пуст', style: TextStyle(color: Colors.red)));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Выбери мир', style: _hdr),
      const SizedBox(height: 4),
      Text('От выбора мира зависят расы, классы и правила игры',
        style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
      const SizedBox(height: 12),
      ..._worlds.map((w) => _worldCard(w)),
    ]);
  }

  Widget _worldCard(Map<String, dynamic> w) {
    final key = (w['key'] ?? '').toString();
    final sel = _selectedWorld == key;
    final name = (w['name'] ?? key).toString();
    final tierName = (w['tier_name'] ?? _tierLabel(w['tier'])).toString();
    final techLevel = (w['tech_level'] ?? '').toString();
    final description = (w['description'] ?? '').toString();
    final descShort = description.length > 100 ? '${description.substring(0, 100)}…' : description;
    final magic = (w['magic_density'] as num?)?.toDouble() ?? 0.0;

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: _loadingWorldData ? null : () => _showWorldDetail(w),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.2), width: sel ? 2 : 1),
            color: sel ? AppTheme.gold.withValues(alpha: 0.15) : Colors.transparent,
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(_worldEmoji(w), style: const TextStyle(fontSize: 18)),
              const SizedBox(width: 8),
              Expanded(child: Text(name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 14))),
              if (sel) const Icon(Icons.check_circle, color: AppTheme.gold, size: 18),
            ]),
            const SizedBox(height: 2),
            Text('Уровень магии: $tierName · Технологии: ${_translateTechLevel(techLevel)} · Магия ×$magic',
              style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11)),
            if (descShort.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(descShort, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 11, height: 1.3),
                maxLines: 2, overflow: TextOverflow.ellipsis),
            ],
          ]),
        ),
      ),
    );
  }

  void _showWorldDetail(Map<String, dynamic> w) {
    final key = (w['key'] ?? '').toString();
    final name = (w['name'] ?? key).toString();
    final emoji = _worldEmoji(w);

    // Контент из API: особенности, описание, правила, картинки
    final rawFeatures = (_worldContent['features'] as Map? ?? {})[key];
    final features = rawFeatures is String ? rawFeatures : '';
    final rawDescriptions = (_worldContent['descriptions'] as Map? ?? {})[key];
    final descriptions = rawDescriptions is String ? rawDescriptions : '';
    final rawRules = (_worldContent['rules'] as Map? ?? {})[key];
    final rules = rawRules is String ? rawRules : (rawRules is Map ? rawRules.toString() : '');
    final images = (_worldContent['images'] as Map? ?? {})[key] as String? ?? '';
    final description = descriptions.isNotEmpty ? descriptions : (w['description'] ?? '').toString();
    final baseUrl = AppConfig.baseUrl;

    final ruleLines = rules
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty && (l.startsWith('-') || l.startsWith('—')))
        .toList();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A1A),
        titlePadding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
        contentPadding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
        actionsPadding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2))),
        title: Row(children: [
          Text('$emoji ', style: const TextStyle(fontSize: 22)),
          Expanded(child: Text(name, style: const TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold))),
        ]),
        content: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          const Divider(color: AppTheme.gold),

          // Картинка мира (если есть)
          if (images.isNotEmpty) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.network(
                '$baseUrl$images',
                width: double.infinity,
                height: 200,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox(height: 200, child: Center(child: Text('🖼️', style: TextStyle(fontSize: 48)))),
                loadingBuilder: (_, child, progress) => progress == null ? child : const SizedBox(height: 200, child: Center(child: CircularProgressIndicator())),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Особенности мира
          if (features.isNotEmpty) ...[
            const Text('Особенности мира', style: TextStyle(color: AppTheme.gold, fontSize: 15, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(features, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.85), fontSize: 13, height: 1.4, fontStyle: FontStyle.italic)),
            const SizedBox(height: 16),
          ],

          // Описание
          if (description.isNotEmpty) ...[
            const Text('Описание', style: TextStyle(color: AppTheme.gold, fontSize: 15, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(description, style: const TextStyle(color: AppTheme.parchment, fontSize: 13, height: 1.5)),
            const SizedBox(height: 16),
          ],

          // Особые правила
          if (ruleLines.isNotEmpty) ...[
            const Text('Особые правила', style: TextStyle(color: AppTheme.gold, fontSize: 15, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            ...ruleLines.map((l) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(l, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.8), fontSize: 12, height: 1.3)),
            )),
          ],
        ])),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Закрыть', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5))),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold),
            onPressed: () {
              Navigator.pop(ctx);
              _onWorldSelected(key);
            },
            child: const Text('Выбрать этот мир', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  // ─────────────────────── RACE PICKER ───────────────────────
  Widget _racePicker() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(_selectedWorld == 'warhammer_40k' ? 'Фракция' : 'Раса', style: _hdr),
      const SizedBox(height: 8),
      ..._races.map((r) => _raceTile(r)),
    ]);
  }

  Widget _raceTile(SrdRace race) {
    final sel = _selectedRace == race.name;
    final expanded = sel && race.hasSubraces && race.subraces.isNotEmpty;
    return Padding(padding: const EdgeInsets.only(bottom: 4), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      InkWell(borderRadius: BorderRadius.circular(8), onTap: () => _onRaceChanged(race.name),
        child: Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.2), width: sel ? 2 : 1),
          color: sel ? AppTheme.gold.withValues(alpha: 0.15) : Colors.transparent,
        ), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(race.name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 14))),
            if (race.hasSubraces) Icon(sel ? Icons.expand_less : Icons.expand_more, color: AppTheme.gold, size: 18),
          ]),
          if (race.statBonuses.isNotEmpty) ...[const SizedBox(height: 2), Text(_fmtB(race.statBonuses), style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11))],
        ]))),
      if (sel && race.description.isNotEmpty) ...[const SizedBox(height: 6), _desc(race.description)],
      if (sel && race.flavor.isNotEmpty) ...[const SizedBox(height: 4), _flavor(race.flavor)],
      if (expanded) ...[
        const SizedBox(height: 6),
        const Text('  Подраса', style: _subHdr),
        const SizedBox(height: 4),
        ...race.subraces.map((sr) => _subraceInline(sr)),
      ],
    ]));
  }

  Widget _subraceInline(SubracePreview sr) {
    final sel = _selectedSubrace == sr.key;
    return Padding(padding: const EdgeInsets.only(left: 16, bottom: 4), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      InkWell(borderRadius: BorderRadius.circular(6), onTap: () => _onSubraceChanged(sr),
        child: Container(padding: const EdgeInsets.symmetric(vertical: 7, horizontal: 10), decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.15), width: sel ? 2 : 1),
          color: sel ? AppTheme.gold.withValues(alpha: 0.12) : Colors.transparent,
        ), child: Row(children: [
          Icon(sel ? Icons.radio_button_checked : Icons.radio_button_unchecked, color: sel ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.4), size: 16),
          const SizedBox(width: 8),
          Expanded(child: Text(sr.name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 13))),
          if (sr.statBonuses.isNotEmpty) Text(_fmtB(sr.statBonuses), style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11)),
        ]))),
      if (sel && sr.desc.isNotEmpty) ...[const SizedBox(height: 4), Padding(padding: const EdgeInsets.only(left: 24), child: _desc(sr.desc))],
    ]));
  }

  // ─────────────────────── CLASS PICKER ───────────────────────
  Widget _classPicker() {
    final filtered = _selectedWorld == 'warhammer_40k'
        ? (_selectedRace != null
            ? _classes.where((c) => c.name.startsWith('$_selectedRace: ')).toList()
            : <SrdClass>[])
        : _classes;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(_selectedWorld == 'warhammer_40k' ? 'Класс (для фракции $_selectedRace)' : 'Класс', style: _hdr),
      const SizedBox(height: 8),
      if (filtered.isEmpty)
        Padding(
          padding: const EdgeInsets.all(12),
          child: Text('Сначала выберите фракцию', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)),
        )
      else
        ...filtered.map((c) => _classTile(c)),
    ]);
  }

  Widget _classTile(SrdClass cls) {
    final sel = _selectedClass == cls.name;
    final subData = _subclasses[cls.name];
    final subs = subData?.options ?? [];
    final expanded = sel && subs.isNotEmpty;
    return Padding(padding: const EdgeInsets.only(bottom: 4), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      InkWell(borderRadius: BorderRadius.circular(8), onTap: () => _onClassChanged(cls.name),
        child: Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.2), width: sel ? 2 : 1),
          color: sel ? AppTheme.gold.withValues(alpha: 0.15) : Colors.transparent,
        ), child: Row(children: [
          Expanded(child: Text(cls.name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 14))),
          Text('кХ ${cls.hitDie}', style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.4), fontSize: 12)),
          const SizedBox(width: 8),
          Icon(expanded ? Icons.expand_less : Icons.expand_more, color: AppTheme.gold.withValues(alpha: 0.3), size: 18),
        ]))),
      if (sel && cls.description.isNotEmpty) ...[const SizedBox(height: 6), _desc(cls.description)],
      if (sel && cls.flavor.isNotEmpty) ...[const SizedBox(height: 4), _flavor(cls.flavor)],
      if (expanded) ...[
        const SizedBox(height: 8),
        if (subData!.flavor.isNotEmpty) ...[Padding(padding: const EdgeInsets.only(left: 8), child: _flavor(subData.flavor)), const SizedBox(height: 6)],
        Text('  ${subData.label}', style: const TextStyle(color: AppTheme.gold, fontSize: 13, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        ...subs.map((opt) => _subclassInline(opt)),
      ],
    ]));
  }

  Widget _subclassInline(SubclassPreview opt) {
    final sel = _selectedSubclass == opt.key;
    return Padding(padding: const EdgeInsets.only(left: 16, bottom: 4), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      InkWell(borderRadius: BorderRadius.circular(6), onTap: () => setState(() => _selectedSubclass = opt.key),
        child: Container(padding: const EdgeInsets.symmetric(vertical: 7, horizontal: 10), decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.15), width: sel ? 2 : 1),
          color: sel ? AppTheme.gold.withValues(alpha: 0.12) : Colors.transparent,
        ), child: Row(children: [
          Icon(sel ? Icons.radio_button_checked : Icons.radio_button_unchecked, color: sel ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.4), size: 16),
          const SizedBox(width: 8),
          Expanded(child: Text(opt.name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 13))),
        ]))),
      if (sel && opt.desc.isNotEmpty) ...[const SizedBox(height: 4), Padding(padding: const EdgeInsets.only(left: 24), child: _desc(opt.desc))],
    ]));
  }

  // ─────────────────────── STATS ────────────────────────────
  Widget _statsBlock() {
    final rem = _pointsRemaining();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Text('Характеристики (Point Buy 27)', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
        const Spacer(),
        Text('$rem/$_totalPoints', style: TextStyle(color: rem == 0 ? Colors.green : (rem < 0 ? Colors.red : AppTheme.gold), fontWeight: FontWeight.bold, fontSize: 15)),
        TextButton.icon(onPressed: _applyStandardArray, icon: const Icon(Icons.auto_fix_high, size: 14), label: const Text('Массив', style: TextStyle(fontSize: 12)), style: TextButton.styleFrom(foregroundColor: AppTheme.gold.withValues(alpha: 0.6))),
      ]),
      const SizedBox(height: 8),
      ..._statOrder.map((s) => _statRow(s)),
    ]);
  }

  Widget _statRow(String stat) {
    final base = _baseStats[stat]!;
    final bonus = _activeStatBonuses[stat] ?? 0;
    final fv = base + bonus;
    return Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Row(children: [
      SizedBox(width: 50, child: Text(_statNames[stat]!, style: const TextStyle(color: AppTheme.parchment, fontWeight: FontWeight.bold))),
      SizedBox(width: 32, child: IconButton(icon: const Icon(Icons.remove_circle_outline, size: 20), color: _canDec(stat) ? AppTheme.gold : Colors.grey, padding: EdgeInsets.zero, onPressed: _canDec(stat) ? () => setState(() => _baseStats[stat] = _baseStats[stat]! - 1) : null)),
      SizedBox(width: 28, child: Text('$base', textAlign: TextAlign.center, style: const TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold))),
      SizedBox(width: 32, child: IconButton(icon: const Icon(Icons.add_circle_outline, size: 20), color: _canInc(stat) ? AppTheme.gold : Colors.grey, padding: EdgeInsets.zero, onPressed: _canInc(stat) ? () => setState(() => _baseStats[stat] = _baseStats[stat]! + 1) : null)),
      SizedBox(width: 90, child: RichText(text: TextSpan(children: [
        TextSpan(text: '$fv', style: TextStyle(color: fv > 15 ? Colors.greenAccent : Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        if (bonus > 0) TextSpan(text: ' (+$bonus)', style: TextStyle(color: Colors.greenAccent.withValues(alpha: 0.6), fontSize: 11)),
      ]))),
      SizedBox(width: 40, child: Text(_modStr(fv), style: TextStyle(color: fv >= 12 ? Colors.green : (fv <= 9 ? Colors.red : AppTheme.parchment), fontSize: 16, fontWeight: FontWeight.bold), textAlign: TextAlign.right)),
      SizedBox(width: 36, child: Text('${_pointBuyCost[base] ?? 0} о', textAlign: TextAlign.right, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 11))),
    ]));
  }

  // ─────────────────────── SKILLS ───────────────────────────
  Widget _skillsBlock() {
    // Load spell info if needed (lazy — simulate caster detection from class)
    if (_selectedClass != null && !_isCaster) {
      // Classes that get spells at level 1
      const casterClasses = {'Волшебник', 'Жрец', 'Друид', 'Бард', 'Чародей', 'Колдун'};
      if (casterClasses.contains(_selectedClass)) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) setState(() {
            _isCaster = true;
            _castingAbility = _castingAbilityForClass(_selectedClass!);
            // We'll load available spells from setStats API response
            // For now, load from /srd/spells
            _loadAvailableSpells();
          });
        });
      }
    }

    // Уникальные навыки мира, доступные выбранной расе И выбранному классу
    final filteredWorldSkills = _worldSkillsForClass();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Выбери $_skillsToPick ${_skillsToPick == 1 ? 'навык' : 'навыка'} (${_selectedClass ?? "?"})', style: const TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      Text('Выбрано: ${_chosenSkills.length}/$_skillsToPick', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5))),
      const SizedBox(height: 12),
      if (_worldSkills.isNotEmpty) ...[
        // Уникальные умения мира — только доступные выбранной расе И выбранному классу
        if (filteredWorldSkills.isNotEmpty)
          ...filteredWorldSkills.map((s) => _worldSkillSelectable(s))
        else ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text('Для этой расы и класса уникальных навыков нет',
              style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 12, fontStyle: FontStyle.italic)),
          ),
          // Фоллбек: стандартный выбор навыков класса — как в else-ветке
          if (_classSkills.isNotEmpty) ..._classSkillCards(),
        ],
      ] else if (_classSkills.isNotEmpty)
        ..._classSkillCards()
      else
        Text('Класс не загружен или навыки не указаны', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4))),
      const Divider(color: AppTheme.gold, height: 32),
      // Languages
      const Text('Языки', style: TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 4, children: _chosenLanguages.map((l) => Chip(
        label: Text(l, style: const TextStyle(fontSize: 12)),
        deleteIcon: const Icon(Icons.close, size: 14),
        onDeleted: () => setState(() => _chosenLanguages.remove(l)),
        backgroundColor: AppTheme.gold.withValues(alpha: 0.15),
        labelStyle: const TextStyle(color: AppTheme.gold),
        side: const BorderSide(color: AppTheme.gold, width: 0.5),
      )).toList()),
      const SizedBox(height: 12),
      if (_worldLanguages.isNotEmpty) ...[
        const Text('Языки мира', style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        ..._worldLanguagesForRace().map((l) => _worldLangChip(l)),
      ] else ...[
        const Text('Стандартные', style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        ..._standardLanguages.map((l) => _langChip(l)),
        const SizedBox(height: 12),
        const Text('Экзотические', style: TextStyle(color: AppTheme.gold, fontSize: 14, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        ..._exoticLanguages.map((l) => _langChip(l)),
      ],
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: TextField(controller: _langCtrl, style: const TextStyle(color: AppTheme.parchment, fontSize: 13),
          decoration: InputDecoration(hintText: 'Свой язык...', hintStyle: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.3), fontSize: 13), isDense: true,
            enabledBorder: const UnderlineInputBorder(borderSide: BorderSide(color: AppTheme.gold))))),
        IconButton(onPressed: () { if (_langCtrl.text.isNotEmpty) { setState(() => _chosenLanguages.add(_langCtrl.text.trim())); _langCtrl.clear(); } },
          icon: const Icon(Icons.add_circle, color: AppTheme.gold, size: 22)),
      ]),
    ]);
  }

  /// Уникальные навыки мира, доступные выбранной расе И выбранному классу.
  /// «Смешанная» раса — фильтр по расе не применяется. Сравнение без учёта
  /// регистра, пробелов и ё/е.
  List<Map<String, dynamic>> _worldSkillsForClass() {
    final all = _worldSkills.whereType<Map<String, dynamic>>().toList();
    final cls = _selectedClass;
    final race = _selectedRace;
    bool eq(String a, String b) =>
        a.trim().toLowerCase().replaceAll('ё', 'е') ==
        b.trim().toLowerCase().replaceAll('ё', 'е');

    final byClass = all.where((s) {
      final sc = (s['class'] ?? '').toString();
      return cls == null || sc.isEmpty || eq(sc, cls);
    }).toList();

    if (race == null || race.isEmpty || race == 'Смешанная') return byClass;
    return byClass.where((s) {
      final races = (s['races'] as List?) ?? const [];
      return races.any((r) => eq(r.toString(), race));
    }).toList();
  }

  /// Карточки стандартных навыков класса (общий код для else-ветки и фоллбека).
  List<Widget> _classSkillCards() {
    return _classSkills.map((key) {
      final info = _skillCatalog[key];
      final name = info?['name'] ?? key;
      final stat = info?['stat'];
      final icon = _statIcons[stat] ?? '🎯';
      final checked = _chosenSkills.contains(key);
      final canCheck = checked || _chosenSkills.length < _skillsToPick;
      return Card(
        color: checked ? AppTheme.gold.withValues(alpha: 0.1) : Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: checked ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.08))),
        margin: const EdgeInsets.only(bottom: 4),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: canCheck ? () => setState(() { if (checked) _chosenSkills.remove(key); else _chosenSkills.add(key); }) : null,
          child: Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6), child: Row(children: [
            SizedBox(width: 28, child: Text(icon, style: const TextStyle(fontSize: 16))),
            const SizedBox(width: 4),
            Expanded(child: Text(name, style: TextStyle(color: checked ? AppTheme.gold : AppTheme.parchment, fontWeight: checked ? FontWeight.bold : FontWeight.normal, fontSize: 13))),
            if (info != null)
              IconButton(icon: const Icon(Icons.info_outline, size: 16), color: AppTheme.gold.withValues(alpha: 0.4), padding: EdgeInsets.zero, constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                onPressed: () => _showSkillDetail(key, info)),
            if (checked) const Icon(Icons.check_circle, color: AppTheme.gold, size: 18),
          ])),
        ),
      );
    }).toList();
  }

  Widget _langChip(String lang) {
    final picked = _chosenLanguages.contains(lang);
    return Padding(padding: const EdgeInsets.only(right: 6, bottom: 4), child: FilterChip(
      label: Text(lang, style: TextStyle(color: picked ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
      selected: picked, selectedColor: AppTheme.gold.withValues(alpha: 0.15), checkmarkColor: AppTheme.gold,
      side: BorderSide(color: picked ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.1)),
      onSelected: (v) => setState(() { if (v) _chosenLanguages.add(lang); else _chosenLanguages.remove(lang); }),
      visualDensity: VisualDensity.compact, materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    ));
  }

  /// Языки мира, доступные выбранной расе. Если раса не выбрана — все языки мира.
  List<Map<String, dynamic>> _worldLanguagesForRace() {
    final all = _worldLanguages.whereType<Map<String, dynamic>>().toList();
    final race = _selectedRace;
    if (race == null || race.isEmpty) return all;
    final forRace = all.where((l) {
      final races = (l['races'] as List?) ?? [];
      return races.any((r) => _normRace(r.toString()) == _normRace(race));
    }).toList();
    return forRace.isNotEmpty ? forRace : all;
  }

  /// Выбираемая плитка уникального навыка мира.
  Widget _worldSkillSelectable(Map<String, dynamic> s) {
    final key = (s['key'] ?? s['name'] ?? '').toString();
    final stat = (s['stat'] ?? '').toString();
    final icon = _statIcons[stat] ?? '✦';
    final name = (s['name'] ?? '').toString();
    final label = stat.isNotEmpty ? '$name (${_statNames[stat] ?? stat})' : name;
    final checked = _chosenSkills.contains(key);
    final canCheck = checked || _chosenSkills.length < _skillsToPick;
    final desc = (s['desc'] ?? '').toString();
    return Card(
      color: checked ? AppTheme.gold.withValues(alpha: 0.1) : Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: checked ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.08))),
      margin: const EdgeInsets.only(bottom: 4),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: canCheck ? () => setState(() { if (checked) _chosenSkills.remove(key); else _chosenSkills.add(key); }) : null,
        child: Padding(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6), child: Row(children: [
          SizedBox(width: 28, child: Text(icon, style: const TextStyle(fontSize: 16))),
          const SizedBox(width: 4),
          Expanded(child: Text(label, style: TextStyle(color: checked ? AppTheme.gold : AppTheme.parchment, fontWeight: checked ? FontWeight.bold : FontWeight.normal, fontSize: 13))),
          if (desc.isNotEmpty)
            IconButton(icon: const Icon(Icons.info_outline, size: 16), color: AppTheme.gold.withValues(alpha: 0.4), padding: EdgeInsets.zero, constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
              onPressed: () => _showWorldSkillDetail(s)),
          if (checked) const Icon(Icons.check_circle, color: AppTheme.gold, size: 18),
        ])),
      ),
    );
  }

  /// Чип языка мира — выбираемый, с подсказкой (скрипт/описание) по тапу.
  Widget _worldLangChip(Map<String, dynamic> l) {
    final name = (l['name'] ?? '').toString();
    final script = (l['script'] ?? '').toString();
    final desc = (l['description'] ?? '').toString();
    final picked = _chosenLanguages.contains(name);
    return Padding(
      padding: const EdgeInsets.only(right: 6, bottom: 4),
      child: Tooltip(
        message: [if (script.isNotEmpty) 'Письмо: $script', if (desc.isNotEmpty) desc].join('\n'),
        child: FilterChip(
          label: Text(name, style: TextStyle(color: picked ? AppTheme.gold : AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
          selected: picked,
          selectedColor: AppTheme.gold.withValues(alpha: 0.15),
          checkmarkColor: AppTheme.gold,
          side: BorderSide(color: picked ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.1)),
          backgroundColor: Colors.transparent,
          onSelected: (v) => setState(() { if (v) _chosenLanguages.add(name); else _chosenLanguages.remove(name); }),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      ),
    );
  }

  void _showSkillDetail(String key, Map<String, String> info) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: AppTheme.darkBrown,
      title: Text(info['name']!, style: const TextStyle(color: AppTheme.gold)),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Характеристика: ${_statNames[info['stat']] ?? info['stat']}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5))),
        const SizedBox(height: 8),
        Text(info['desc']!, style: const TextStyle(color: AppTheme.parchment)),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK', style: TextStyle(color: AppTheme.gold)))],
    ));
  }

  void _showWorldSkillDetail(Map<String, dynamic> s) {
    final stat = (s['stat'] ?? '').toString();
    final desc = (s['desc'] ?? '').toString();
    final name = (s['name'] ?? '').toString();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: AppTheme.darkBrown,
      title: Text(name, style: const TextStyle(color: AppTheme.gold)),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (stat.isNotEmpty) ...[
          Text('Характеристика: ${_statNames[stat] ?? stat}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5))),
          const SizedBox(height: 8),
        ],
        if (desc.isNotEmpty) Text(desc, style: const TextStyle(color: AppTheme.parchment)),
      ]),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK', style: TextStyle(color: AppTheme.gold)))],
    ));
  }

  // ─────────────────────── SPELLS ───────────────────────────
  Future<void> _loadAvailableSpells() async {
    if (_selectedClass == null) return;
    try {
      final api = ref.read(chatApiServiceProvider);
      final spells = await api.getSrdSpells(_selectedClass!);
      // Filter level 0-1 spells only (first level caster)
      final filtered = spells.where((s) => s.level <= 1).toList();
      if (mounted) setState(() {
        _availableSpells = filtered;
        // Default limits
        _maxCantrips = _cantripsForClass(_selectedClass!);
        _maxLevel1 = _level1SpellsForClass(_selectedClass!);
      });
    } catch (_) {}
  }

  int _cantripsForClass(String cn) {
    switch (cn) { case 'Чародей': return 4; case 'Волшебник': return 3; case 'Колдун': return 2; case 'Друид': case 'Жрец': return 3; case 'Бард': return 2; default: return 0; }
  }
  int _level1SpellsForClass(String cn) {
    switch (cn) { case 'Волшебник': return 6; case 'Жрец': case 'Друид': return 4; case 'Бард': return 4; case 'Чародей': return 2; case 'Колдун': return 2; default: return 0; }
  }
  String _castingAbilityForClass(String cn) {
    switch (cn) { case 'Волшебник': return 'ИНТ'; case 'Жрец': case 'Друид': return 'МУД'; case 'Бард': case 'Чародей': case 'Колдун': return 'ХАР'; default: return ''; }
  }

  Widget _spellsBlock() {
    if (_availableSpells.isEmpty) {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('✨ Заклинания', style: TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ElevatedButton.icon(onPressed: _loadAvailableSpells, icon: const Icon(Icons.refresh, size: 16), label: const Text('Загрузить заклинания'), style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold.withValues(alpha: 0.2))),
      ]);
    }
    final cantripCount = _chosenSpells.where((k) => _spellLevelForKey(k) == 0).length;
    final spellCount = _chosenSpells.where((k) => _spellLevelForKey(k) > 0).length;

    // Group by level
    final grouped = <int, List<SrdSpellData>>{};
    for (final s in _availableSpells) {
      grouped.putIfAbsent(s.level, () => []).add(s);
    }
    final levels = grouped.keys.toList()..sort();

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('✨ Выбери заклинания', style: TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      Text('Базовый параметр: $_castingAbility', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
      const SizedBox(height: 4),
      Text('Заговоры: $cantripCount / $_maxCantrips    Заклинания: $spellCount / $_maxLevel1',
        style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 12)),
      const SizedBox(height: 12),
      ...levels.map((lvl) {
        final label = lvl == 0 ? 'Заговоры (бесконечно)' : '${lvl} уровень';
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 13, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          ...grouped[lvl]!.map((s) => _spellCard(s)),
          const SizedBox(height: 8),
        ]);
      }),
    ]);
  }

  Widget _spellCard(SrdSpellData s) {
    final checked = _chosenSpells.contains(s.key);
    final isCantrip = s.level == 0;
    final atLimit = !checked && (isCantrip
        ? _chosenSpells.where((k) => _spellLevelForKey(k) == 0).length >= _maxCantrips
        : _chosenSpells.where((k) => _spellLevelForKey(k) > 0).length >= _maxLevel1);

    return Card(
      color: checked ? AppTheme.gold.withValues(alpha: 0.1) : Colors.transparent,
      margin: const EdgeInsets.only(bottom: 2),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: checked ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.08))),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: atLimit ? null : () => setState(() { if (checked) _chosenSpells.remove(s.key); else _chosenSpells.add(s.key); }),
        child: Padding(padding: const EdgeInsets.all(10), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(s.name, style: TextStyle(color: checked ? AppTheme.gold : AppTheme.parchment, fontWeight: checked ? FontWeight.bold : FontWeight.normal, fontSize: 13))),
            if (s.school.isNotEmpty)
              Text(s.school, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.4), fontSize: 11)),
            if (atLimit) Text(' лимит', style: TextStyle(color: Colors.red.withValues(alpha: 0.5), fontSize: 11)),
            if (checked) const Padding(padding: EdgeInsets.only(left: 4), child: Icon(Icons.check_circle, color: AppTheme.gold, size: 16)),
          ]),
          if (s.descText != null) ...[const SizedBox(height: 4), Text(s.descText!, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11, height: 1.3), maxLines: 2, overflow: TextOverflow.ellipsis)],
        ])),
      ),
    );
  }

  // ─────────────────────── NAME ────────────────────────────
  /// Нормализация имени расы для сопоставления (ё ↔ е).
  static String _normRace(String s) => s.replaceAll('ё', 'е').replaceAll('Ё', 'Е');

  /// Мировые предыстории для расы (с ё-нормализацией ключа) или null.
  List<dynamic>? _worldBgsForRace(String race) {
    final direct = _worldBackgrounds[race];
    if (direct != null) return direct;
    for (final entry in _worldBackgrounds.entries) {
      if (_normRace(entry.key) == _normRace(race)) return entry.value;
    }
    return null;
  }

  /// Предыстории для выбора: мировые (для выбранной расы) или стандартные SRD.
  List<SrdBackground> get _availableBackgrounds {
    if (_worldBackgrounds.isNotEmpty) {
      final race = _selectedRace;
      // Мировые предыстории: только для выбранной расы (если она есть в данных мира)
      if (race != null) {
        final raw = _worldBgsForRace(race);
        if (raw != null) {
          final list = raw
              .whereType<Map<String, dynamic>>()
              .map((j) => SrdBackground.fromJson(_normalizeWorldBg(j)))
              .toList();
          if (list.isNotEmpty) return list;
        }
      }
    }
    return _backgrounds; // стандартные SRD-предыстории
  }

  /// Мировая предыстория: {name, description, skills, tools, feat, feat_desc} → формат SrdBackground.
  Map<String, dynamic> _normalizeWorldBg(Map<String, dynamic> j) => {
    'name': j['name'] ?? '',
    'skills': j['skills'] ?? [],
    'equipment': j['equipment'] ?? j['tools'] ?? [],
    'feature': j['feat'] ?? '',
    'feature_desc': j['feat_desc'] ?? '',
    'flavor': j['description'] ?? '',
  };

  Widget _backgroundPicker() {
    final bgs = _availableBackgrounds;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Предыстория', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 4),
      Text('Выбери происхождение — AI создаст историю персонажа', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
      const SizedBox(height: 12),
      if (bgs.isEmpty)
        Text('Нет доступных предысторий', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4)))
      else
        ...bgs.map((bg) => _bgCard(bg)),
      const SizedBox(height: 16),
      TextField(
        controller: _backstoryCtrl,
        maxLines: 3,
        style: const TextStyle(color: AppTheme.parchment, fontSize: 14),
        decoration: const InputDecoration(
          hintText: 'Или опиши сам (необязательно)...',
          hintStyle: TextStyle(color: AppTheme.parchment),
        ),
      ),
    ]);
  }

  Widget _bgCard(SrdBackground bg) {
    final sel = _selectedBg == bg.name;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => setState(() => _selectedBg = bg.name),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: sel ? AppTheme.gold : AppTheme.gold.withValues(alpha: 0.2), width: sel ? 2 : 1),
            color: sel ? AppTheme.gold.withValues(alpha: 0.15) : Colors.transparent,
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(bg.name, style: TextStyle(color: sel ? AppTheme.gold : AppTheme.parchment, fontWeight: sel ? FontWeight.bold : FontWeight.normal, fontSize: 14))),
              if (sel) const Icon(Icons.check_circle, color: AppTheme.gold, size: 18),
            ]),
            if (bg.skills.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Навыки: ${bg.skills.take(3).join(", ")}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 11)),
            ],
            if (bg.feature.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(bg.feature, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 11)),
            ],
          ]),
        ),
      ),
    );
  }

  Widget _nameField() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Имя персонажа', style: TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      TextField(controller: _nameCtrl, style: const TextStyle(color: AppTheme.parchment, fontSize: 20),
        decoration: const InputDecoration(hintText: 'Введите имя', labelStyle: TextStyle(color: AppTheme.gold))),
      if (_selectedRace != null && _selectedClass != null) ...[
        const SizedBox(height: 12),
        _preview(),
      ],
    ]);
  }

  Widget _preview() {
    final dexMod = _modifier(_finalStat('dex'));
    final conMod = _modifier(_finalStat('con'));
    final clsObj = _classes.firstWhere((c) => c.name == _selectedClass, orElse: () => _classes.isNotEmpty ? _classes[0] : SrdClass(name: '', description: '', hitDie: 8, proficiencies: {}, features: [], startingEquipment: {}));
    final hitDie = (int.tryParse(clsObj.hitDie.toString()) ?? 8);
    final hp = hitDie + conMod + ((_level - 1) * (hitDie ~/ 2 + 1));
    return Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(8), border: Border.all(color: AppTheme.gold.withValues(alpha: 0.3))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('$_selectedRace ${_selectedClass!}', style: const TextStyle(color: AppTheme.gold, fontSize: 14)),
        const SizedBox(height: 4),
        Text('HP: ${hp > 0 ? hp : 1}  AC: ${10 + dexMod}  Ур: $_level', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 13)),
      ]));
  }

  // ─── Style helpers ───
  static const _hdr = TextStyle(color: AppTheme.gold, fontSize: 16, fontWeight: FontWeight.bold);
  static const _subHdr = TextStyle(color: AppTheme.gold, fontSize: 13, fontWeight: FontWeight.bold);

  Widget _desc(String t) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
    decoration: BoxDecoration(borderRadius: BorderRadius.circular(6), color: AppTheme.gold.withValues(alpha: 0.05), border: Border.all(color: AppTheme.gold.withValues(alpha: 0.1))),
    child: Text(t, style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.85), fontSize: 12, height: 1.4)),
  );

  Widget _flavor(String t) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(borderRadius: BorderRadius.circular(6), border: Border(left: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3), width: 2))),
    child: Text(t, style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.6), fontSize: 11, fontStyle: FontStyle.italic, height: 1.4)),
  );

  String _fmtB(Map<String, int> b) => b.entries.map((e) => '+${e.value} ${_statNames[e.key] ?? e.key}').join(', ');
}
