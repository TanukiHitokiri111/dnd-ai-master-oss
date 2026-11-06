import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:fetch_client/fetch_client.dart';
import '../config/app_config.dart';

class ChatApiException implements Exception {
  final String message;
  final int? statusCode;
  const ChatApiException(this.message, {this.statusCode});
  @override
  String toString() => 'ChatApiException: $message (status: $statusCode)';
}

class ChatSendResult {
  final String reply;
  final bool isDead;
  final int? gold;
  final int? hpCurrent;
  final int? hpMax;
  final String? imageUrl;
  final String? appearanceUrl;
  final String? npcUrl;
  final String? npcName;
  final Map<String, dynamic>? diceRoll;
  final int? level;
  final int? xp;
  final int? xpGained;
  final bool leveledUp;
  const ChatSendResult({required this.reply, this.isDead = false, this.gold, this.hpCurrent, this.hpMax, this.imageUrl, this.appearanceUrl, this.npcUrl, this.npcName, this.diceRoll, this.level, this.xp, this.xpGained, this.leveledUp = false});
}

// ─── SSE-стриминг: события ───
sealed class ChatStreamEvent {}
class ChatStreamDelta extends ChatStreamEvent {
  final String text;
  ChatStreamDelta(this.text);
}
class ChatStreamDone extends ChatStreamEvent {
  final ChatSendResult result;
  ChatStreamDone(this.result);
}
class ChatStreamError extends ChatStreamEvent {
  final String message;
  ChatStreamError(this.message);
}

// ─── Data classes ───

class DiceRollData {
  final List<int> dice, results;
  final int modifier;
  final String label;
  final bool advantage, disadvantage;
  const DiceRollData({required this.dice, required this.results, this.modifier = 0, this.label = '', this.advantage = false, this.disadvantage = false});
  Map<String, dynamic> toJson() => {'dice': dice, 'results': results, 'modifier': modifier, 'label': label, 'advantage': advantage, 'disadvantage': disadvantage};
}

class ItemData {
  final int id;
  final String itemKey, itemName, itemType, itemSubtype, slot;
  final int qty;
  final bool equipped, attunement;
  final String notes;
  final Map<String, dynamic>? modifiers;
  final String flavor;
  const ItemData({required this.id, required this.itemKey, required this.itemName, required this.itemType,
    required this.itemSubtype, required this.qty, required this.slot, required this.equipped,
    this.attunement = false, this.notes = '', this.modifiers, this.flavor = ''});
  factory ItemData.fromJson(Map<String, dynamic> j) => ItemData(
    id: j['id'] ?? 0, itemKey: j['item_key'] ?? '', itemName: j['item_name'] ?? '',
    itemType: j['item_type'] ?? 'gear', itemSubtype: j['item_subtype'] ?? '',
    qty: j['qty'] ?? 1, slot: j['slot'] ?? 'inventory',
    equipped: j['equipped'] == true || j['equipped'] == 1,
    attunement: j['attunement'] == true || j['attunement'] == 1,
    notes: j['notes'] ?? '',
    modifiers: j['modifiers'] is Map ? Map<String,dynamic>.from(j['modifiers']) : null,
    flavor: j['flavor'] ?? '');
}

class CharacterData {
  final String id, userId, name, race, className, backgroundName;
  final String world;
  final int level, hpMax, hpCurrent, ac, initAc, speed, gold;
  final Map<String, dynamic>? xpToNext;
  final Map<String, int> stats;
  final String backstory;
  final List<Map<String, dynamic>> features;
  final Map<String, dynamic> proficiencies;
  final List<String> skillProficiencies, languages;
  final List<ItemData> items;
  final String createdAt, updatedAt;
  final bool isDead;
  const CharacterData({
    required this.id, required this.userId, required this.name, required this.race,
    required this.className, this.backgroundName = '', required this.level,
    required this.stats, required this.hpMax, required this.hpCurrent, required this.ac,
    this.initAc = 10, this.speed = 30, this.gold = 0, this.backstory = '',
    this.features = const [], this.proficiencies = const {},
    this.skillProficiencies = const [], this.languages = const [],
    this.items = const [], this.createdAt = '', this.updatedAt = '', this.isDead = false,
    this.world = '',
    this.xpToNext,
  });
  factory CharacterData.fromJson(Map<String, dynamic> j) => CharacterData(
    id: j['id'] ?? '', userId: j['user_id'] ?? '', name: j['name'] ?? '',
    race: j['race'] ?? '', className: j['class_name'] ?? '',
    backgroundName: j['background_name'] ?? '', level: j['level'] ?? 1,
    stats: Map<String,int>.from(j['stats'] ?? {}),
    hpMax: j['hp_max'] ?? 1, hpCurrent: j['hp_current'] ?? 1, ac: j['ac'] ?? 10,
    initAc: j['init_ac'] ?? j['ac'] ?? 10, speed: j['speed'] ?? 30, gold: j['gold'] ?? 0,
    backstory: j['backstory'] ?? '',
    features: (j['features'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    proficiencies: j['proficiencies'] is Map ? Map<String,dynamic>.from(j['proficiencies']) : {},
    skillProficiencies: (j['skill_proficiencies'] as List?)?.cast<String>() ?? [],
    languages: (j['languages'] as List?)?.cast<String>() ?? [],
    items: (j['items'] as List?)?.map((i) => ItemData.fromJson(i)).toList() ?? [],
    createdAt: j['created_at'] ?? '', updatedAt: j['updated_at'] ?? '',
    isDead: j['is_dead'] == true || j['is_dead'] == 1,
    world: j['world'] ?? '',
    xpToNext: j['xp_to_next'] is Map ? Map<String, dynamic>.from(j['xp_to_next']) : null,
  );

  int get modifierStr => ((stats['str'] ?? 10) - 10) ~/ 2;
  int get modifierDex => ((stats['dex'] ?? 10) - 10) ~/ 2;
  int get modifierCon => ((stats['con'] ?? 10) - 10) ~/ 2;
  int get modifierInt => ((stats['int'] ?? 10) - 10) ~/ 2;
  int get modifierWis => ((stats['wis'] ?? 10) - 10) ~/ 2;
  int get modifierCha => ((stats['cha'] ?? 10) - 10) ~/ 2;
  int modifier(String stat) => ((stats[stat] ?? 10) - 10) ~/ 2;
}

class SrdTrait { final String name; final String desc; final String flavor; const SrdTrait({required this.name, required this.desc, this.flavor=''}); factory SrdTrait.fromJson(Map<String, dynamic> j) => SrdTrait(name: j['name']??'', desc: j['desc']??'', flavor: j['flavor']??''); }

class SrdBackground { final String name; final List<String> skills; final List<Map> equipment; final String feature, featureDesc, flavor; const SrdBackground({required this.name, required this.skills, required this.equipment, required this.feature, required this.featureDesc, this.flavor=''});
  factory SrdBackground.fromJson(Map<String, dynamic> j) => SrdBackground(
    name: j['name']??'',
    skills: _parseStringList(j['skills']),
    equipment: _parseEquipmentList(j['equipment']),
    feature: j['feature']??'',
    featureDesc: j['feature_desc']??'',
    flavor: j['flavor']??'',
  );
}

/// Parse a value that can be either a List<String> or a comma-separated String
List<String> _parseStringList(dynamic value) {
  if (value == null) return [];
  if (value is List) return value.cast<String>();
  if (value is String) return value.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
  return [];
}

/// Parse equipment: can be List<Map> or a comma-separated String
List<Map> _parseEquipmentList(dynamic value) {
  if (value == null) return [];
  if (value is List) return value.cast<Map>();
  if (value is String) return value.split(',').map((s) => {'name': s.trim()}).where((e) => (e['name'] as String).isNotEmpty).toList();
  return [];
}

class SrdClass { final String name; final String description; final String flavor; final int hitDie; final Map proficiencies; final List<SrdTrait> features; final Map startingEquipment; const SrdClass({required this.name, required this.description, required this.hitDie, required this.proficiencies, required this.features, required this.startingEquipment, this.flavor = ''}); factory SrdClass.fromJson(Map j) => SrdClass(name: j['name']??'', description: j['description']??'', flavor: j['flavor']??'', hitDie: j['hit_die']??8, proficiencies: j['proficiencies']??{}, features: ((j['features'] as List?)??[]).map((f) => SrdTrait.fromJson(f is Map<String,dynamic> ? f : {})).toList(), startingEquipment: j['starting_equipment']??{}); }

class SrdRace { final String name; final String description; final String flavor; final List<SrdTrait> traits; final Map<String, int> statBonuses; final bool hasSubraces; final List<SubracePreview> subraces; const SrdRace({required this.name, required this.description, required this.traits, this.flavor = '', this.statBonuses = const {}, this.hasSubraces = false, this.subraces = const []}); factory SrdRace.fromJson(Map j) => SrdRace(name: j['name']??'', description: j['description']??'', flavor: j['flavor']??'', traits: ((j['traits'] as List?)??[]).map((t) => SrdTrait.fromJson(t is Map<String,dynamic> ? t : {})).toList(), statBonuses: Map<String,int>.from((j['stat_bonuses'] as Map?)??{}), hasSubraces: j['has_subraces']??false, subraces: ((j['subraces'] as List?)??[]).map((s) => SubracePreview.fromJson(s)).toList()); }

class SubracePreview { final String key; final String name; final String desc; final Map<String, int> statBonuses; const SubracePreview({required this.key, required this.name, this.desc = '', this.statBonuses = const {}}); factory SubracePreview.fromJson(Map j) => SubracePreview(key: j['key']??'', name: j['name']??'', desc: j['desc']??'', statBonuses: Map<String,int>.from((j['stat_bonuses'] as Map?)??{})); }

class SubclassPreview { final String key; final String name; final String desc; const SubclassPreview({required this.key, required this.name, this.desc = ''}); factory SubclassPreview.fromJson(Map j) => SubclassPreview(key: j['key']??'', name: j['name']??'', desc: j['desc']??''); }

class SubclassData { final String label; final String flavor; final List<SubclassPreview> options; const SubclassData({required this.label, this.flavor = '', required this.options}); factory SubclassData.fromJson(Map j) => SubclassData(label: j['label']??'', flavor: j['flavor']??'', options: ((j['options'] as List?)??[]).map((o) => SubclassPreview.fromJson(o is Map<String,dynamic> ? o : {})).toList()); }

class SpellData {
  final int id;
  final String spellKey, spellName, school, castingTime, range, components, duration, source, notes, flavor;
  final int spellLevel;
  final Map<String, dynamic>? desc;
  const SpellData({required this.id, required this.spellKey, required this.spellName, required this.spellLevel, this.school='', this.castingTime='', this.range='', this.components='', this.duration='', this.source='', this.notes='', this.flavor='', this.desc});
  factory SpellData.fromJson(Map<String, dynamic> j) => SpellData(
    id: j['id'] ?? 0, spellKey: j['spell_key'] ?? '', spellName: j['spell_name'] ?? '',
    spellLevel: j['spell_level'] ?? 1, school: j['school'] ?? '',
    castingTime: j['casting_time'] ?? '', range: j['range'] ?? '',
    components: j['components'] ?? '', duration: j['duration'] ?? '',
    source: j['source'] ?? '', notes: j['notes'] ?? '',
    flavor: j['flavor'] ?? '',
    desc: j['desc'] is Map ? Map<String,dynamic>.from(j['desc']) : null,
  );
}

class SrdSpellData {
  final String key, name, school;
  final int level;
  final String? descText;  // plain text description
  final Map<String, dynamic>? desc; // structured description
  final String castingTime, range, components, duration, flavor;
  const SrdSpellData({required this.key, required this.name, required this.level, required this.school, this.desc, this.descText, this.castingTime='', this.range='', this.components='', this.duration='', this.flavor=''});
  factory SrdSpellData.fromJson(Map<String, dynamic> j) {
    final d = j['desc'];
    return SrdSpellData(
    key: j['key'] ?? '', name: j['name'] ?? '', level: j['level'] ?? 0,
    school: j['school'] ?? '',
    descText: d is String ? d : (d is Map ? (d['text'] as String?) : null),
    desc: d is Map ? Map<String,dynamic>.from(d) : null,
    castingTime: j['casting_time'] ?? '', range: j['range'] ?? '',
    components: j['components'] ?? '', duration: j['duration'] ?? '',
    flavor: j['flavor'] ?? '',
  );
  }
}

class StatusData {
  final CharacterData character;
  final List<SpellData> spells;
  final Map<String, dynamic> spellSlots;
  final int spellDc, spellAttack;
  final String castingAbility;
  final Map<String, dynamic> skills;
  final int profBonus;
  final Map<String, int> saves;
  const StatusData({
    required this.character, required this.spells, required this.spellSlots,
    required this.spellDc, required this.spellAttack, required this.castingAbility,
    required this.skills, required this.profBonus, required this.saves,
  });
  factory StatusData.fromJson(Map<String, dynamic> j) => StatusData(
    character: CharacterData.fromJson(j['character'] ?? {}),
    spells: ((j['spells'] as List?) ?? []).map((s) => SpellData.fromJson(s)).toList(),
    spellSlots: j['spell_slots'] is Map ? Map<String,dynamic>.from(j['spell_slots']) : {},
    spellDc: j['spell_dc'] ?? 0, spellAttack: j['spell_attack'] ?? 0,
    castingAbility: j['casting_ability'] ?? '',
    skills: j['skills'] is Map ? Map<String,dynamic>.from(j['skills']) : {},
    profBonus: j['prof_bonus'] ?? 2,
    saves: j['saves'] is Map ? Map<String,int>.from(j['saves']) : {},
  );
}

class StepOneData {
  final String id, name, race, className;
  final int level, hpMax, hpCurrent;
  final int hitDie, hpMaxSuggested;
  final Map<String, int> statsSuggested;
  final List<Map<String, dynamic>> racialTraits, classFeatures, startingEquipment;
  final List<Map<String, dynamic>> backgrounds;
  final Map<String, dynamic> proficiencies, skillChoices;
  final bool isCaster;
  final List<Map<String, dynamic>> availableSpells;
  final Map<String, dynamic> spellSlots;
  final String castingAbility;
  const StepOneData({
    required this.id, required this.name, required this.race, required this.className,
    required this.level, required this.hpMax, required this.hpCurrent,
    required this.racialTraits, required this.classFeatures, required this.proficiencies,
    required this.skillChoices, required this.hitDie, required this.hpMaxSuggested,
    required this.statsSuggested, required this.startingEquipment, required this.backgrounds,
    this.isCaster = false, this.availableSpells = const [], this.spellSlots = const {},
    this.castingAbility = '',
  });
  factory StepOneData.fromJson(Map<String, dynamic> j) => StepOneData(
    id: j['id'] ?? '', name: j['name'] ?? '', race: j['race'] ?? '',
    className: j['class_name'] ?? '', level: j['level'] ?? 1,
    hpMax: j['hp_max'] ?? 1, hpCurrent: j['hp_current'] ?? 1,
    racialTraits: (j['racial_traits'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    classFeatures: (j['class_features'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    proficiencies: j['proficiencies'] is Map ? Map<String,dynamic>.from(j['proficiencies']) : {},
    skillChoices: j['skill_choices'] is Map ? Map<String,dynamic>.from(j['skill_choices']) : {},
    hitDie: j['hit_die'] ?? 8, hpMaxSuggested: j['hp_max_suggested'] ?? 10,
    statsSuggested: j['stats_suggested'] is Map ? Map<String,int>.from(j['stats_suggested']) : {},
    startingEquipment: (j['starting_equipment'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    backgrounds: (j['backgrounds'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    isCaster: j['is_caster'] == true,
    availableSpells: (j['available_spells'] as List?)?.cast<Map<String,dynamic>>() ?? [],
    spellSlots: j['spell_slots'] is Map ? Map<String,dynamic>.from(j['spell_slots']) : {},
    castingAbility: j['casting_ability'] ?? '',
  );
}

// ─── Service ───

class ChatApiService {
  final String primaryUrl;
  final String reserveUrl;
  final http.Client _client;
  String? _token;
  String _currentBaseUrl; // меняется при failover
  bool _usingReserve = false;

  /// Notifier для UI — null = основной, не-null = резервный
  final ValueNotifier<String?> failoverNotifier = ValueNotifier<String?>(null);

  ChatApiService({required String baseUrl, String? reserveUrl, http.Client? client})
      : primaryUrl = baseUrl,
        reserveUrl = reserveUrl ?? baseUrl,
        _currentBaseUrl = baseUrl,
        _client = client ?? http.Client();
  set token(String? t) => _token = t;
  String? get token => _token;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json', 'Accept': 'application/json',
    if (_token != null) 'Authorization': 'Bearer $_token',
  };

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body, {Duration? timeout}) async {
    return await _tryWithFailover(() => _doPost(path, body, timeout: timeout));
  }

  Future<Map<String, dynamic>> _doPost(String path, Map<String, dynamic> body, {Duration? timeout}) async {
    final uri = Uri.parse('$_currentBaseUrl${AppConfig.apiVersion}$path');
    try {
      final r = await _client.post(uri, headers: _headers, body: json.encode(body)).timeout(timeout ?? AppConfig.requestTimeout);
      if (r.statusCode == 200 || r.statusCode == 201 || r.statusCode == 204) {
        if (r.bodyBytes.isEmpty) return {};
        return json.decode(utf8.decode(r.bodyBytes));
      }
      final err = r.bodyBytes.isNotEmpty ? json.decode(utf8.decode(r.bodyBytes)) : {};
      final detail = err['detail'];
      final message = detail is String
          ? detail
          : detail is List && detail.isNotEmpty
              ? (detail[0] is Map ? detail[0]['msg']?.toString() : detail.toString())
              : 'Ошибка ${r.statusCode}';
      throw ChatApiException(message ?? 'Ошибка ${r.statusCode}', statusCode: r.statusCode);
    } on TimeoutException { throw ChatApiException('Сервер не ответил вовремя.'); }
    catch (e) {
      // SocketException / ClientException / любая сетевая ошибка
      if (e is http.ClientException || e.toString().contains('SocketException') || e.toString().contains('WebSocket')) {
        throw ChatApiException('Нет связи с сервером.');
      }
      rethrow;
    }
    on ChatApiException { rethrow; }
    catch (e) { throw ChatApiException('Ошибка: $e'); }
  }

  Future<dynamic> _get(String path, [Map<String,String>? query]) async {
    return await _tryWithFailover(() => _doGet(path, query));
  }

  Future<dynamic> _doGet(String path, [Map<String,String>? query]) async {
    var uri = Uri.parse('$_currentBaseUrl${AppConfig.apiVersion}$path');
    if (query != null) uri = uri.replace(queryParameters: query);
    try {
      final r = await _client.get(uri, headers: _headers).timeout(AppConfig.requestTimeout);
      if (r.statusCode == 200) return json.decode(utf8.decode(r.bodyBytes));
      throw ChatApiException('Ошибка ${r.statusCode}', statusCode: r.statusCode);
    } on TimeoutException { throw ChatApiException('Сервер не ответил.'); }
    catch (e) {
      if (e is http.ClientException || e.toString().contains('SocketException') || e.toString().contains('WebSocket')) {
        throw ChatApiException('Нет связи с сервером.');
      }
      rethrow;
    }
  }

  Future<bool> _put(String path, Map<String, dynamic> body) async {
    try { return await _tryWithFailover(() => _doPut(path, body)); } catch (_) { return false; }
  }
  Future<bool> _doPut(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$_currentBaseUrl${AppConfig.apiVersion}$path');
    final r = await _client.put(uri, headers: _headers, body: json.encode(body)).timeout(const Duration(seconds: 10));
    return r.statusCode == 200;
  }

  Future<bool> _delete(String path) async {
    try { return await _tryWithFailover(() => _doDelete(path)); } catch (_) { return false; }
  }
  Future<bool> _doDelete(String path) async {
    final uri = Uri.parse('$_currentBaseUrl${AppConfig.apiVersion}$path');
    final r = await _client.delete(uri, headers: _headers).timeout(const Duration(seconds: 10));
    return r.statusCode == 200 || r.statusCode == 204;
  }

  // ─── Auth ───
  Future<Map<String, dynamic>> register(String username, String password, [String? boostyLogin]) {
    final body = <String, dynamic>{'username': username, 'password': password};
    if (boostyLogin != null && boostyLogin.isNotEmpty) body['boosty_login'] = boostyLogin;
    return _post('/auth/register', body);
  }
  Future<Map<String, dynamic>> login(String username, String password) => _post('/auth/login', {'username': username, 'password': password});

  // ─── Boosty ───
  Future<Map<String, dynamic>> linkBoosty(String boostyLogin) => _post('/auth/link_boosty', {'boosty_login': boostyLogin});
  Future<Map<String, dynamic>> redeemCode(String code) => _post('/auth/redeem_code', {'code': code});
  Future<Map<String, dynamic>> authStatus() async {
    final r = await _get('/auth/status');
    return r as Map<String, dynamic>;
  }

  // ─── YooKassa Payments ───
  Future<Map<String, dynamic>> createPayment(int days) => _post('/payments/create', {'days': days});
  Future<Map<String, dynamic>> paymentStatus() async {
    final r = await _get('/payments/status');
    return r as Map<String, dynamic>;
  }

  // ─── Admin: Коды доступа ───
  Future<Map<String, dynamic>> generateCodes({int count = 1, int durationDays = 7, String prefix = 'TANUKI', String note = ''}) =>
    _post('/admin/generate_codes', {'count': count, 'duration_days': durationDays, 'prefix': prefix, 'note': note});
  Future<Map<String, dynamic>> listCodes({String status = 'all', int limit = 50, int offset = 0}) async {
    final r = await _get('/admin/codes?status=$status&limit=$limit&offset=$offset');
    return r as Map<String, dynamic>;
  }

  // ─── Worlds ───

  /// Список всех миров. Миры, исключённые из создания персонажей,
  /// фильтруются на фронте (см. CharacterMasterScreen._excludedWorlds).
  Future<List<Map<String, dynamic>>> getWorlds() async {
    final r = await _get('/worlds');
    final list = (r['worlds'] as List?) ?? [];
    return list.whereType<Map<String, dynamic>>().toList();
  }

  /// Полная структура мира: races, classes, subclasses, backgrounds.
  /// GET /characters/worlds/{worldKey}
  Future<Map<String, dynamic>> getWorldData(String worldKey) async {
    final r = await _get('/characters/worlds/$worldKey');
    return r as Map<String, dynamic>;
  }

  /// Атмосферные описания миров + отфильтрованные особенности (GigaChat).
  Future<Map<String, dynamic>> getWorldContent() async {
    final r = await _get('/worlds/content');
    return r as Map<String, dynamic>;
  }

  /// Предметы снаряжения мира. GET /worlds/{worldKey}/equipment
  Future<List<Map<String, dynamic>>> getWorldEquipment(String worldKey) async {
    final r = await _get('/worlds/$worldKey/equipment');
    return (r as List).cast<Map<String, dynamic>>();
  }

  /// Карта мира (регионы/столица/локации). GET /worlds/{worldKey}/map
  Future<Map<String, dynamic>> getWorldMap(String worldKey) async {
    final r = await _get('/worlds/$worldKey/map');
    return Map<String, dynamic>.from(r as Map);
  }

  /// Языки мира с привязкой к расам. GET /worlds/{worldKey}/languages
  Future<List<Map<String, dynamic>>> getWorldLanguages(String worldKey) async {
    final r = await _get('/worlds/$worldKey/languages');
    return (r as List).cast<Map<String, dynamic>>();
  }

  /// Предыстории мира по расам: {раса: [предыстории]}. GET /worlds/{worldKey}/backgrounds
  Future<Map<String, dynamic>> getWorldBackgrounds(String worldKey) async {
    final r = await _get('/worlds/$worldKey/backgrounds');
    return Map<String, dynamic>.from(r as Map);
  }

  /// Уникальные навыки мира. GET /worlds/{worldKey}/skills
  Future<List<Map<String, dynamic>>> getWorldSkills(String worldKey) async {
    final r = await _get('/worlds/$worldKey/skills');
    return (r as List).cast<Map<String, dynamic>>();
  }

  /// Список миров для UI (первые 100 символов описания + иконка).

  // ─── SRD ───
  Future<List<SrdBackground>> getBackgrounds() async {
    final r = await _get('/srd/backgrounds');
    return (r['backgrounds'] as List).map((j) => SrdBackground.fromJson(j)).toList();
  }
  Future<List<SrdClass>> getClasses({String world = ''}) async {
    final query = <String, String>{if (world.isNotEmpty) 'world': world};
    final r = await _get('/srd/classes', query.isNotEmpty ? query : null);
    return (r['classes'] as List).map((j) => SrdClass.fromJson(j)).toList();
  }
  Future<List<SrdRace>> getRaces({bool brief = false, String world = ''}) async {
    final query = <String, String>{
      if (brief) 'brief': 'true',
      if (world.isNotEmpty) 'world': world,
    };
    final r = await _get('/srd/races', query.isNotEmpty ? query : null);
    return (r['races'] as List).map((j) => SrdRace.fromJson(j)).toList();
  }
  Future<Map<String, dynamic>> getSubraces([String? race]) async {
    final path = race != null ? '/srd/subraces?race=${Uri.encodeComponent(race)}' : '/srd/subraces';
    final r = await _get(path);
    return r as Map<String, dynamic>;
  }
  Future<Map<String, SubclassData>> getSubclasses() async {
    final r = await _get('/srd/subclasses');
    final map = r as Map<String, dynamic>;
    final result = <String, SubclassData>{};
    map.forEach((k, v) { result[k] = SubclassData.fromJson(v as Map<String, dynamic>); });
    return result;
  }
  Future<Map<String, dynamic>> getEquipment() async { final r = await _get('/srd/equipment'); return r as Map<String, dynamic>; }

  // ─── Characters v2 ───
  Future<Map<String, dynamic>> createDraft(String name, String race, String className, [String bg = '', String subclass = '', String subrace = '', Map<String, dynamic>? mixedHeritage, String world = '']) =>
    _post('/characters/create', {
      'name': name, 'race': race, 'class_name': className, 'background_name': bg, 'subclass': subclass, 'subrace': subrace,
      if (mixedHeritage != null) 'mixed_heritage': mixedHeritage,
      'world': world,
    });

  // ─── Mixed Heritage ───
  Future<Map<String, dynamic>> rollMixedHeritage(Map<String, int> speciesPercentages, {int? seed}) =>
    _post('/characters/mixed-heritage/roll', {'species_percentages': speciesPercentages, if (seed != null) 'seed': seed});

  Future<Map<String, dynamic>> getMixedHeritageConfig() async {
    final r = await _get('/characters/mixed-heritage/config');
    return r as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getCompatibleRaces(String raceName) async {
    final r = await _get('/characters/mixed-heritage/compatible/${Uri.encodeComponent(raceName)}');
    return r as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> checkMixedCompatibility(Map<String, int> speciesPercentages) async =>
    _post('/characters/mixed-heritage/check', {'species_percentages': speciesPercentages});

  // ─── SRD Spells ───
  Future<List<SrdSpellData>> getSrdSpells([String? casterClass, int? level]) async {
    var path = '/srd/spells';
    final params = <String,String>{};
    if (casterClass != null) params['class_name'] = casterClass;
    if (level != null) params['level'] = level.toString();
    if (params.isNotEmpty) path += '?${params.entries.map((e) => '${e.key}=${e.value}').join('&')}';
    final r = await _get(path);
    return (r['spells'] as List).map((j) => SrdSpellData.fromJson(j)).toList();
  }

  // ─── Spells CRUD ───
  Future<List<SpellData>> listSpells(String charId) async {
    final r = await _get('/characters/$charId/spells');
    return (r as List).map((j) => SpellData.fromJson(j)).toList();
  }

  Future<SpellData> addSpell(String charId, String spellKey, {String source='manual', String notes=''}) async {
    final r = await _post('/characters/$charId/spells', {'spell_key': spellKey, 'source': source, 'notes': notes});
    return SpellData.fromJson(r);
  }

  Future<bool> removeSpell(String charId, int spellId) => _delete('/characters/$charId/spells/$spellId');

  // ─── Features ───
  Future<void> addFeature(String charId, String name, String desc, {String source='mid-game'}) =>
    _post('/characters/$charId/features', {'name': name, 'desc': desc, 'source': source});

  // ─── Status ───
  Future<StatusData> getStatus(String charId) async {
    final r = await _get('/characters/$charId/status');
    return StatusData.fromJson(r);
  }

  Future<Map<String, dynamic>> setStats(String charId, Map<String,int> stats, List<String> skills, List<String> langs) =>
    _post('/characters/$charId/stats', {'stats': stats, 'skill_proficiencies': skills, 'languages': langs});

  Future<Map<String, dynamic>> finalizeCharacter(String charId, String backstory, String bgName) =>
    _post('/characters/$charId/finalize?background_name=$bgName', {'backstory': backstory});

  Future<List<CharacterData>> listCharacters() async {
    final r = await _get('/characters');
    return (r['characters'] as List).map((j) => CharacterData.fromJson(j)).toList();
  }

  Future<CharacterData> getCharacter(String id) async {
    final r = await _get('/characters/$id');
    return CharacterData.fromJson(r);
  }

  Future<void> updateCharacter(String id, Map<String, dynamic> data) => _put('/characters/$id', data);
  Future<bool> deleteCharacter(String id) => _delete('/characters/$id');

  // ─── Level-up / Multiclass ───
  /// Классы, доступные для мультикласса в мире персонажа (уже взятые исключены).
  Future<List<String>> getMulticlassClasses(String charId) async {
    final r = await _get('/characters/$charId/multiclass-classes');
    final list = (r['classes'] as List?) ?? const [];
    return list.cast<String>();
  }

  Future<Map<String, dynamic>> levelUp(String charId, {String? newClass, int? hpRoll, Map<String, int>? statIncrease, String? featChoice, List<String>? spellChoices, List<String>? skillChoices}) =>
    _post('/characters/$charId/level-up', {
      if (newClass != null) 'new_class': newClass,
      if (hpRoll != null) 'hp_roll': hpRoll,
      if (statIncrease != null) 'stat_increase': statIncrease,
      if (featChoice != null) 'feat_choice': featChoice,
      if (spellChoices != null) 'spell_choices': spellChoices,
      if (skillChoices != null) 'skill_choices': skillChoices,
    });

  // ─── Inventory ───
  Future<ItemData> addItem(String charId, String itemKey, {String slot='inventory', int qty=1}) async {
    final r = await _post('/characters/$charId/items', {'item_key': itemKey, 'qty': qty, 'slot': slot});
    return ItemData.fromJson(r);
  }
  Future<List<ItemData>> listItems(String charId) async {
    final r = await _get('/characters/$charId/items');
    return (r as List).map((j) => ItemData.fromJson(j)).toList();
  }
  Future<bool> removeItem(String charId, int itemId) => _delete('/characters/$charId/items/$itemId');

  // ─── Chat ───
  Future<ChatSendResult> sendMessage({required String userId, required String message, String? characterId, DiceRollData? diceRoll}) async {
    final body = <String, dynamic>{'user_id': userId, 'message': message};
    if (characterId != null) body['character_id'] = characterId;
    if (diceRoll != null) body['dice_roll'] = diceRoll.toJson();
    final r = await _post('/chat', body, timeout: AppConfig.chatRequestTimeout);
    return ChatSendResult(
      reply: r['reply'] as String,
      isDead: r['is_dead'] == true || r['is_dead'] == 1,
      gold: r['gold'] is int ? r['gold'] as int : null,
      hpCurrent: r['hp_current'] is int ? r['hp_current'] as int : null,
      hpMax: r['hp_max'] is int ? r['hp_max'] as int : null,
      imageUrl: r['image_url'] as String?,
      appearanceUrl: r['appearance_url'] as String?,
      npcUrl: r['npc_url'] as String?,
      npcName: r['npc_name'] as String?,
      diceRoll: r['dice_roll'] is Map<String, dynamic> ? r['dice_roll'] as Map<String, dynamic> : null,
      level: r['level'] is int ? r['level'] as int : null,
      xp: r['xp'] is int ? r['xp'] as int : null,
      xpGained: r['xp_gained'] is int ? r['xp_gained'] as int : null,
      leveledUp: r['leveled_up'] == true || r['leveled_up'] == 1,
    );
  }
  Future<void> clearHistory(String userId) async {
    await _delete('/chat/history/$userId');
  }

  // ─── Chat: SSE-стриминг ───
  /// Стриминг ответа: yield'ит [ChatStreamDelta] по мере генерации,
  /// в конце — [ChatStreamDone] с полным результатом (теги уже обработаны).
  Stream<ChatStreamEvent> streamMessage({required String userId, required String message, String? characterId, DiceRollData? diceRoll}) async* {
    final body = <String, dynamic>{'user_id': userId, 'message': message};
    if (characterId != null) body['character_id'] = characterId;
    if (diceRoll != null) body['dice_roll'] = diceRoll.toJson();

    final http.Client client = kIsWeb
        ? FetchClient(mode: RequestMode.cors)
        : http.Client();
    try {
      final uri = Uri.parse('$_currentBaseUrl${AppConfig.apiVersion}/chat/stream');
      final request = http.Request('POST', uri)
        ..headers.addAll(_headers)
        ..headers['Content-Type'] = 'application/json'
        ..headers['Accept'] = 'text/event-stream'
        ..body = jsonEncode(body);

      final response = await client.send(request).timeout(AppConfig.chatRequestTimeout);
      if (response.statusCode != 200) {
        final errBody = await response.stream.bytesToString();
        throw ChatApiException('Сервер вернул ${response.statusCode}: $errBody', statusCode: response.statusCode);
      }

      String buffer = '';
      await for (final chunk in response.stream.transform(utf8.decoder)) {
        buffer += chunk;
        // SSE: события разделяются двойным \n
        while (buffer.contains('\n\n')) {
          final idx = buffer.indexOf('\n\n');
          final rawEvent = buffer.substring(0, idx);
          buffer = buffer.substring(idx + 2);
          if (rawEvent.isEmpty) continue;
          final event = _parseSseEvent(rawEvent);
          if (event != null) yield event;
        }
      }
      // Хвост (последнее событие без финального \n\n)
      if (buffer.trim().isNotEmpty) {
        final event = _parseSseEvent(buffer);
        if (event != null) yield event;
      }
    } finally {
      client.close();
    }
  }

  ChatStreamEvent? _parseSseEvent(String raw) {
    String data = '';
    String eventName = 'message';
    for (final line in raw.split('\n')) {
      if (line.startsWith('data:')) {
        data += line.substring(5).trim();
      } else if (line.startsWith('event:')) {
        eventName = line.substring(6).trim();
      }
    }
    if (data.isEmpty) return null;
    try {
      final json = jsonDecode(data) as Map<String, dynamic>;
      if (eventName == 'error') {
        return ChatStreamError(json['detail'] as String? ?? 'Ошибка сервера');
      }
      final type = json['type'];
      if (type == 'delta') {
        final text = json['text'] as String? ?? '';
        if (text.isNotEmpty) return ChatStreamDelta(text);
        return null;
      }
      if (type == 'done') {
        final r = json['response'] as Map<String, dynamic>;
        return ChatStreamDone(_parseChatResult(r));
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  ChatSendResult _parseChatResult(Map<String, dynamic> r) => ChatSendResult(
    reply: r['reply'] as String? ?? '',
    isDead: r['is_dead'] == true || r['is_dead'] == 1,
    gold: r['gold'] is int ? r['gold'] as int : null,
    hpCurrent: r['hp_current'] is int ? r['hp_current'] as int : null,
    hpMax: r['hp_max'] is int ? r['hp_max'] as int : null,
    imageUrl: r['image_url'] as String?,
    appearanceUrl: r['appearance_url'] as String?,
    npcUrl: r['npc_url'] as String?,
    npcName: r['npc_name'] as String?,
    diceRoll: r['dice_roll'] is Map<String, dynamic> ? r['dice_roll'] as Map<String, dynamic> : null,
    level: r['level'] is int ? r['level'] as int : null,
    xp: r['xp'] is int ? r['xp'] as int : null,
    xpGained: r['xp_gained'] is int ? r['xp_gained'] as int : null,
    leveledUp: r['leveled_up'] == true || r['leveled_up'] == 1,
  );

  // ─── Multiplayer: Sessions ───
  Future<Map<String, dynamic>> createSession(String name) => _post('/sessions', {'name': name});
  Future<List<Map<String, dynamic>>> listSessions() async {
    final r = await _get('/sessions');
    return ((r['sessions'] ?? []) as List).cast<Map<String, dynamic>>();
  }
  Future<Map<String, dynamic>> getSession(String id) async {
    final r = await _get('/sessions/$id');
    return r as Map<String, dynamic>;
  }
  Future<Map<String, dynamic>> joinSession(String inviteCode) =>
      _post('/sessions/join', {'invite_code': inviteCode});
  Future<bool> leaveSession(String id) => _delete('/sessions/$id/leave');
  Future<bool> deleteSession(String sessionId) => _delete('/sessions/$sessionId');
  Future<Map<String, dynamic>> setReady(String sessionId, String characterId) =>
      _post('/sessions/$sessionId/ready', {'character_id': characterId});
  Future<Map<String, dynamic>> startSession(String id) => _post('/sessions/$id/start', {});
  Future<Map<String, dynamic>> rollInitiative(String id) => _post('/sessions/$id/initiative', {});
  Future<Map<String, dynamic>> nextTurn(String id) => _post('/sessions/$id/next-turn', {});
  Future<Map<String, dynamic>> getSessionMessages(String id, {int limit = 100}) async {
    final r = await _get('/sessions/$id/messages?limit=$limit');
    return r as Map<String, dynamic>;
  }

  // ─── Multiplayer: Friends ───
  Future<List<Map<String, dynamic>>> getFriends() async {
    final r = await _get('/friends');
    final friends = (r['friends'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final pending = (r['pending'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final sent = (r['sent'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    return [...friends, ...pending, ...sent];
  }
  Future<Map<String, dynamic>> sendFriendRequest(String username) =>
      _post('/friends/request', {'username': username});
  Future<bool> acceptFriend(int requestId) async {
    final r = await _post('/friends/accept/$requestId', {});
    return r['ok'] == true;
  }
  Future<bool> rejectFriend(int requestId) async {
    final r = await _post('/friends/reject/$requestId', {});
    return r['ok'] == true;
  }
  Future<bool> removeFriend(String friendUserId) => _delete('/friends/$friendUserId');

  Future<List<Map<String, dynamic>>> searchUsers(String query) async {
    final r = await _get('/friends/search?q=$query');
    return ((r['users'] ?? []) as List).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> inviteFriendToSession(String sessionId, String friendUserId) =>
      _post('/friends/invite_to_session/$sessionId', {'friend_user_id': friendUserId});

  /// При ошибке соединения переключается на резервный сервер и повторяет
  Future<T> _tryWithFailover<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on ChatApiException catch (e) {
      // Только ошибки соединения триггерят failover (не 4xx/5xx)
      if (_isConnectionError(e) && !_usingReserve && reserveUrl != primaryUrl) {
        _switchToReserve();
        return await request();
      }
      rethrow;
    }
  }

  // ─── Quests ───

  Future<List<Map<String, dynamic>>> listQuests(String charId) async {
    final r = await _get('/characters/$charId/quests');
    return (r as List).cast<Map<String, dynamic>>();
  }

  // ─── World map (персонажа) ───

  /// Карта мира для персонажа. GET /characters/{charId}/map
  Future<Map<String, dynamic>> getCharacterMap(String charId) async {
    final r = await _get('/characters/$charId/map');
    return Map<String, dynamic>.from(r as Map);
  }

  // ─── Abilities ───
  /// Умения персонажа: points / learned / available / next
  Future<Map<String, dynamic>> getAbilities(String charId) async {
    final r = await _get('/characters/$charId/abilities');
    return Map<String, dynamic>.from(r as Map);
  }

  /// Вложить очки в умения. ranks — сколько рангов ДОБАВИТЬ.
  Future<Map<String, dynamic>> allocateAbilities(
      String charId, String classKey, List<Map<String, dynamic>> allocations) async {
    final r = await _post('/characters/$charId/abilities/allocate',
        {'class_key': classKey, 'allocations': allocations});
    return Map<String, dynamic>.from(r as Map);
  }

  /// Полное описание умения со всеми 5 рангами
  Future<Map<String, dynamic>> getAbilityDetail(String charId, String abilityKey) async {
    final r = await _get('/characters/$charId/abilities/$abilityKey');
    return Map<String, dynamic>.from(r as Map);
  }

  bool _isConnectionError(ChatApiException e) =>
      e.message.contains('Нет связи') || e.message.contains('не ответил');

  void _switchToReserve() {
    _currentBaseUrl = reserveUrl;
    _usingReserve = true;
    failoverNotifier.value = reserveUrl;
  }

  /// Возвращает true если сейчас используется резервный сервер
  bool get isUsingReserve => _usingReserve;

  void dispose() => _client.close();
}
