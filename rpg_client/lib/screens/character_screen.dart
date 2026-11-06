import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/auth_provider.dart';
import '../providers/chat_provider.dart';
import '../providers/api_service_provider.dart';
import '../services/chat_api_service.dart';
import '../theme/app_theme.dart';
import 'abilities_screen.dart';

class CharacterScreen extends ConsumerStatefulWidget {
  const CharacterScreen({super.key});
  @override
  ConsumerState<CharacterScreen> createState() => _CharacterScreenState();
}

class _CharacterScreenState extends ConsumerState<CharacterScreen> {
  List<CharacterData> _chars = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadChars();
  }

  Future<void> _loadChars() async {
    setState(() { _loading = true; _error = null; });
    try {
      _chars = await ref.read(chatApiServiceProvider).listCharacters();
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _loading = false);
  }

  void _select(CharacterData c) {
    ref.read(chatProvider.notifier).setCharacter(c);
    Navigator.pushReplacementNamed(context, '/chat');
  }

  void _openInventory(CharacterData c) {
    Navigator.pushNamed(context, '/inventory', arguments: {
      'characterId': c.id,
      'characterName': c.name,
      'gold': c.gold,
      'itemsJson': json.encode(c.items.map((i) => {
        'id': i.id, 'item_key': i.itemKey, 'item_name': i.itemName,
        'item_type': i.itemType, 'item_subtype': i.itemSubtype,
        'qty': i.qty, 'slot': i.slot, 'equipped': i.equipped,
        'attunement': i.attunement, 'notes': i.notes,
        'modifiers': i.modifiers, 'flavor': i.flavor,
      }).toList()),
    });
  }

  void _openQuests(CharacterData c) {
    Navigator.pushNamed(context, '/quests', arguments: {
      'characterId': c.id,
      'characterName': c.name,
    });
  }

  void _openMap(CharacterData c) {
    Navigator.pushNamed(context, '/map', arguments: {
      'characterId': c.id,
      'characterName': c.name,
    });
  }

  void _openAbilities(CharacterData c) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => AbilitiesScreen(
      characterId: c.id,
      classKey: c.className,
      characterName: c.name,
    )));
  }

  Future<void> _deleteChar(CharacterData c) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Удалить персонажа?', style: TextStyle(color: AppTheme.gold)),
        content: Text('${c.name}, ${c.race} ${c.className} (ур. ${c.level}) будет удалён безвозвратно.',
          style: const TextStyle(color: AppTheme.parchment)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          TextButton(onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Удалить', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await ref.read(chatApiServiceProvider).deleteCharacter(c.id);
      setState(() => _chars.removeWhere((x) => x.id == c.id));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Ошибка: $e')));
      }
    }
  }

  // Используем старый упрощённый экран для быстрого создания
  void _createSimple() async {
    final result = await Navigator.pushNamed(context, '/character_create');
    if (result == true) _loadChars();
  }

  // Новый расширенный визард
  void _createWizard() async {
    final result = await Navigator.pushNamed(context, '/character_wizard');
    if (result == true) _loadChars();
  }

  String _modStr(int val) {
    final m = (val - 10) ~/ 2;
    return m >= 0 ? '+$m' : '$m';
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      appBar: AppBar(
        title: const Text('Мои персонажи'),
        actions: [
          if (auth.isLoggedIn)
            IconButton(
              icon: const Icon(Icons.groups, color: AppTheme.gold),
              tooltip: 'Мои партии',
              onPressed: () => Navigator.pushNamed(context, '/sessions'),
            ),
          if (auth.isLoggedIn)
            TextButton(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              child: Text(auth.username ?? '', style: const TextStyle(color: AppTheme.gold)),
            )
          else
            TextButton(
              onPressed: () => Navigator.pushReplacementNamed(context, '/login'),
              child: const Text('Войти', style: TextStyle(color: AppTheme.gold)),
            ),
        ],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: AppTheme.gold))
        : _error != null
          ? _buildError()
          : Column(
              children: [
                Expanded(
                  child: _chars.isEmpty
                    ? _buildEmpty()
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                        itemCount: _chars.length * 2 + 1,
                        itemBuilder: (ctx, i) {
                          if (i == _chars.length * 2) return _buildCreateSection();
                          final c = _chars[i ~/ 2];
                          if (i.isOdd) return _buildInventoryCard(c);
                          return _buildCharacterCard(c);
                        },
                      ),
                ),
              ],
            ),
    );
  }

  Widget _buildCharacterCard(CharacterData c) {
    return Dismissible(
      key: Key(c.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        color: Colors.red.shade900,
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      confirmDismiss: (_) async {
        await _deleteChar(c);
        return false;
      },
      child: Card(
        color: AppTheme.darkBrown,
        margin: const EdgeInsets.only(bottom: 8),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.2))),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => _select(c),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(backgroundColor: AppTheme.gold, radius: 16, child: Text('${c.level}', style: const TextStyle(color: Colors.black, fontSize: 13, fontWeight: FontWeight.bold))),
                    const SizedBox(width: 10),
                    Expanded(child: Text(c.name, style: const TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 16))),
                    const Icon(Icons.chevron_right, color: AppTheme.gold, size: 20),
                  ],
                ),
                const SizedBox(height: 4),
                Text('${c.race} ${c.className}', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 13)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _statChip('❤️', '${c.hpCurrent}/${c.hpMax} HP'),
                    const SizedBox(width: 12),
                    _statChip('🛡️', 'AC ${c.ac}'),
                    const SizedBox(width: 12),
                    _statChip('💰', '${c.gold} зм'),
                  ],
                ),
                _buildXpBar(c),
                if (c.backstory.isNotEmpty || c.backgroundName.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  GestureDetector(
                    onTap: () => _showBackstory(c),
                    child: Text(
                      c.backstory.isNotEmpty
                        ? '📜 ${c.backstory.length > 80 ? '${c.backstory.substring(0, 80)}...' : c.backstory}'
                        : '📜 ${c.backgroundName}',
                      style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.45), fontSize: 11, fontStyle: FontStyle.italic)),
                  ),
                ],
                const SizedBox(height: 4),
                Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  children: ['str', 'dex', 'con', 'int', 'wis', 'cha'].map((key) {
                    final labels = {'str': 'СИЛ', 'dex': 'ЛОВ', 'con': 'ТЕЛ', 'int': 'ИНТ', 'wis': 'МУД', 'cha': 'ХАР'};
                    final val = c.stats[key] ?? 10;
                    final mod = _modStr(val);
                    return Text('${labels[key]} $mod', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 10));
                  }).toList(),
                ),
                if (c.items.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text('🎒 ${c.items.map((i) => i.itemName).take(4).join(', ')}${c.items.length > 4 ? '...' : ''}',
                    style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.4), fontSize: 11)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showBackstory(CharacterData c) {
    final text = c.backstory.isNotEmpty ? c.backstory : 'Предыстория: ${c.backgroundName}';
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: Text('📜 ${c.name}', style: const TextStyle(color: AppTheme.gold)),
        content: SingleChildScrollView(
          child: Text(text, style: const TextStyle(color: AppTheme.parchment, fontSize: 14, height: 1.5)),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Закрыть')),
        ],
      ),
    );
  }

  void _showRedeemCodeDialog() {
    final ctrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Ввести код доступа', style: TextStyle(color: AppTheme.gold)),
        content: TextField(
          controller: ctrl,
          style: const TextStyle(color: AppTheme.parchment),
          decoration: const InputDecoration(
            labelText: 'Код',
            hintText: 'TANUKI-XXXX-XXXX',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
          TextButton(onPressed: () async {
            Navigator.pop(ctx);
            final result = await ref.read(authProvider.notifier).redeemCode(ctrl.text.trim());
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result ?? 'OK')));
            }
          }, child: const Text('Активировать')),
        ],
      ),
    );
  }

  Widget _statChip(String icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: AppTheme.gold.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)),
      child: Text('$icon $text', style: const TextStyle(color: AppTheme.gold, fontSize: 12)),
    );
  }

  Widget _buildXpBar(CharacterData c) {
    final xp = c.xpToNext;
    if (xp == null) return const SizedBox.shrink();
    final span = xp['span'];
    final into = xp['into'];
    final needed = xp['needed'];
    if (span == null || into == null || needed == null) {
      // Максимальный уровень — показываем просто текст
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text('⭐ Ур. ${c.level} — макс. уровень',
          style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.5), fontSize: 11)),
      );
    }
    final progress = span == 0 ? 0.0 : (into / span).clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 12, color: AppTheme.gold),
              const SizedBox(width: 4),
              Text('${c.level} ур.', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.6), fontSize: 11)),
              const Spacer(),
              Text('$into/$span XP до ${c.level + 1} ур.',
                style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.7), fontSize: 11)),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              backgroundColor: AppTheme.parchment.withValues(alpha: 0.12),
              valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.gold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInventoryCard(CharacterData c) {
    return Card(
      color: AppTheme.gold.withValues(alpha: 0.05),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.15))),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(children: [
          Row(children: [
          // Inventory button
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _openInventory(c),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(children: [
                  const Icon(Icons.backpack, color: AppTheme.gold, size: 22),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('🎒 Инвентарь', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
                      Text(
                        c.items.isNotEmpty ? '${c.items.length} предметов' : 'Пусто',
                        style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 11),
                      ),
                    ]),
                  ),
                  const Icon(Icons.chevron_right, color: AppTheme.gold, size: 18),
                ]),
              ),
            ),
          ),
          Container(width: 1, height: 32, color: AppTheme.gold.withValues(alpha: 0.15)),
          // Quests button
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _openQuests(c),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(children: [
                  const Icon(Icons.flag, color: AppTheme.gold, size: 22),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('📜 Квесты', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
                      Text('Журнал', style: TextStyle(color: AppTheme.parchment, fontSize: 11)),
                    ]),
                  ),
                  const Icon(Icons.chevron_right, color: AppTheme.gold, size: 18),
                ]),
              ),
            ),
          ),
          Container(width: 1, height: 32, color: AppTheme.gold.withValues(alpha: 0.15)),
          // Map button
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _openMap(c),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(children: [
                  const Icon(Icons.map, color: AppTheme.gold, size: 22),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('🗺️ Карта', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
                      Text('Мир', style: TextStyle(color: AppTheme.parchment, fontSize: 11)),
                    ]),
                  ),
                  const Icon(Icons.chevron_right, color: AppTheme.gold, size: 18),
                ]),
              ),
            ),
          ),
          ]), // end Row 1 (Инвентарь/Квесты + Карта)
          const SizedBox(height: 8),
          // Abilities button — вторая строка
          Row(children: [
            Expanded(
              child: InkWell(
                borderRadius: BorderRadius.circular(10),
                onTap: () => _openAbilities(c),
                child: const Padding(
                  padding: EdgeInsets.all(8),
                  child: Row(children: [
                    Icon(Icons.bolt, color: AppTheme.gold, size: 22),
                    SizedBox(width: 8),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('⚡ Умения', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 14)),
                        Text('Ранги и очки', style: TextStyle(color: AppTheme.parchment, fontSize: 11)),
                      ]),
                    ),
                    Icon(Icons.chevron_right, color: AppTheme.gold, size: 18),
                  ]),
                ),
              ),
            ),
          ]), // end Row 2 (Умения)
        ]),
      ),
    );
  }

  Widget _buildError() {
    if (_error != null && _error!.contains('403')) {
      // Пользователь заблокирован — показываем активацию вместо ошибки
      return _buildActivationScreen();
    }
    return Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.cloud_off, size: 64, color: Colors.red),
      const SizedBox(height: 16),
      Text(_error ?? 'Ошибка', style: const TextStyle(color: Colors.red, fontSize: 16)),
      const SizedBox(height: 8),
      Text('Не удалось загрузить персонажей', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.4), fontSize: 13)),
      const SizedBox(height: 24),
      ElevatedButton.icon(
        onPressed: _loadChars,
        icon: const Icon(Icons.refresh),
        label: const Text('Повторить'),
        style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold, foregroundColor: Colors.black),
      ),
    ]),
  );
  }

  Widget _buildActivationScreen() {
    final errorMsg = _error ?? '';
    final bool canActivate = errorMsg.contains('заблокирован') || errorMsg.contains('истек') || errorMsg.contains('подписк') || errorMsg.contains('активируйте') || errorMsg.contains('ЮKassa') || errorMsg.contains('оплат');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const Icon(Icons.lock_outline, size: 48, color: Colors.orange),
          const SizedBox(height: 12),
          const Text('Доступ ограничен', style: TextStyle(color: AppTheme.gold, fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(
            'Для игры нужна оплата через ЮKassa\\nили код доступа.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 14),
          ),
          const SizedBox(height: 24),
          // YooKassa payment button
          _buildPaymentButton(),
          const SizedBox(height: 16),
          const Divider(color: AppTheme.leather),
          const SizedBox(height: 16),
          // Code section
          _buildCodeActivation(),
          const SizedBox(height: 24),
          // Retry button
          OutlinedButton.icon(
            onPressed: _loadChars,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Проверить снова'),
            style: OutlinedButton.styleFrom(foregroundColor: AppTheme.gold, side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3))),
          ),
        ],
      ),
    );
  }

  Widget _buildPaymentButton() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.gold.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.gold.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.payment, color: AppTheme.gold, size: 18),
            SizedBox(width: 8),
            Text('Оплатить через ЮKassa', style: TextStyle(color: AppTheme.gold, fontWeight: FontWeight.bold, fontSize: 15)),
          ]),
          const SizedBox(height: 4),
          Text('7₽ × день. Карты, СБП, ЮMoney.', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.pushNamed(context, '/payment'),
              icon: const Icon(Icons.credit_card, size: 18),
              label: const Text('Выбрать и оплатить'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.gold,
                foregroundColor: Colors.black,
                minimumSize: const Size(double.infinity, 44),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCodeActivation() {
    final codeCtrl = TextEditingController();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.leather.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.leather.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.vpn_key, color: AppTheme.leather, size: 18),
            const SizedBox(width: 8),
            const Text('Код доступа', style: TextStyle(color: AppTheme.leather, fontWeight: FontWeight.bold, fontSize: 15)),
          ]),
          const SizedBox(height: 4),
          Text('Если у вас есть код — введите здесь', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 12)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: TextField(
                controller: codeCtrl,
                style: const TextStyle(color: AppTheme.parchment, fontSize: 14),
                decoration: const InputDecoration(
                  hintText: 'TANUKI-XXXX-XXXX',
                  isDense: true,
                  contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
              ),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () async {
                final code = codeCtrl.text.trim();
                if (code.isEmpty) return;
                final result = await ref.read(authProvider.notifier).redeemCode(code);
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result ?? 'OK')));
                  _loadChars(); // перезагрузить после активации
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.leather, foregroundColor: Colors.black),
              child: const Text('Активировать'),
            ),
          ]),
        ],
      ),
    );
  }

  Widget _buildEmpty() => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.person_add, size: 64, color: AppTheme.gold.withValues(alpha: 0.4)),
      const SizedBox(height: 16),
      Text('У вас пока нет персонажей', style: TextStyle(color: AppTheme.parchment.withValues(alpha: 0.5), fontSize: 18)),
      const SizedBox(height: 24),
      _buildCreateSection(),
    ]),
  );

  Widget _buildCreateSection() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 8),
    child: Column(
      children: [
        ElevatedButton.icon(
          onPressed: _createWizard,
          icon: const Icon(Icons.auto_fix_high),
          label: const Text('✨ Полное создание (визард)'),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.gold, foregroundColor: Colors.black,
            minimumSize: const Size(double.infinity, 48),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _createSimple,
          icon: const Icon(Icons.bolt, size: 18),
          label: const Text('Быстрое создание'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppTheme.gold.withValues(alpha: 0.6),
            side: BorderSide(color: AppTheme.gold.withValues(alpha: 0.3)),
            minimumSize: const Size(double.infinity, 40),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
      ],
    ),
  );
}



