# D&D AI Master — Comprehensive UI Test Checklist

> Составлен по исходникам Flutter-клиента: `rpg_client/lib/`
> Routes defined in `app.dart`, screens in `screens/`, API service in `services/chat_api_service.dart`

---

## App Routing Overview (`app.dart`)
| Route | Screen | Arguments | Auth Required |
|---|---|---|---|
| `/login` | `LoginScreen` | none | No |
| `/characters` | `CharacterScreen` | none | Yes |
| `/character_create` | `CharacterCreateScreen` | none | Yes |
| `/character_wizard` | `CharacterWizardScreen` | none | Yes |
| `/inventory` | `InventoryScreen` | `characterId`, `characterName`, `itemsJson` | Yes |
| `/status` | `StatusScreen` | `characterId`, `characterName` | Yes |
| `/chat` | `ChatScreen` | none | Yes |

**Initial Route:** `/login` if not logged in, `/characters` if logged in

---

## 1. Login Screen (`login_screen.dart`) — Route: `/login`

### Widgets
| # | Widget | Type | Expected Behavior |
|---|---|---|---|
| 1.1 | 📖 App icon | `Icon(Icons.auto_stories)` | Gold, 64px, 60% opacity |
| 1.2 | "D&D AI Master" title | `Text` | Gold, 28pt, bold |
| 1.3 | Логин field | `TextField` | Parchment text, prefix person icon, label "Логин" |
| 1.4 | Пароль field | `TextField` | Obscured text, prefix lock icon, label "Пароль" |
| 1.5 | Submit button | `ElevatedButton` | Gold bg, black text. Shows "Войти" or "Создать аккаунт" |
| 1.6 | Toggle mode link | `TextButton` | Toggles between login/register modes |
| 1.7 | Error message | `Text` (conditional) | Red text (AppTheme.bloodRed), shown when `state.error != null` |
| 1.8 | Loading spinner | `CircularProgressIndicator` | Replaces button text when `state.isLoading` |

### State Behavior
- **Idle:** Both fields empty, button shows "Войти" (login mode) or "Создать аккаунт" (register mode)
- **Loading:** Button disabled, shows spinner
- **Error:** Red error text appears below password field
- **Success (logged in):** Auto-navigates to `/characters` via `Navigator.pushReplacementNamed`

### API Calls
| Action | Endpoint | Method | Body |
|---|---|---|---|
| Login | `POST /api/v1/auth/login` | `_post` | `{username, password}` |
| Register | `POST /api/v1/auth/register` | `_post` | `{username, password}` |

### Error States to Test
- [ ] Empty username → button does nothing (`user.isEmpty \|\| pass.isEmpty` returns early)
- [ ] Empty password → button does nothing
- [ ] Invalid credentials → server returns error, red text shown
- [ ] Network timeout → `ChatApiException('Сервер не ответил вовремя.')`
- [ ] No network → `ChatApiException('Нет связи с сервером.')`
- [ ] Register with existing username → server error
- [ ] Rapid double-tap on submit → should be safe (button disabled during loading)

---

## 2. Character Screen (`character_screen.dart`) — Route: `/characters`

### Widgets
| # | Widget | Type | Expected Behavior |
|---|---|---|---|
| 2.1 | AppBar title | `Text` | "Мои персонажи" |
| 2.2 | Username button (logged in) | `TextButton` | Shows username in gold, tap → logout |
| 2.3 | "Войти" button (logged out) | `TextButton` | Navigates to `/login` |
| 2.4 | Loading spinner | `CircularProgressIndicator` | Gold, centered, shown while `_loading` |
| 2.5 | Empty state icon | `Icon(Icons.person_add)` | 64px, gold 40% opacity |
| 2.6 | Empty state text | `Text` | "У вас пока нет персонажей" |
| 2.7 | Character cards | `Card` + `InkWell` | Gold border, shows level avatar, name, race+class, HP, AC, stats, items |
| 2.8 | Level avatar | `CircleAvatar` | Gold circle with level number |
| 2.9 | HP/AC chips | Container chips | "❤️ HP: X/Y", "🛡️ AC N" |
| 2.10 | Stat row | `Wrap` of `Text` | Shows СИЛ/ЛОВ/ТЕЛ/ИНТ/МУД/ХАР with modifiers |
| 2.11 | Items preview | `Text` | "🎒 item1, item2..." (max 4 shown) |
| 2.12 | Swipe-to-delete | `Dismissible` | Red background with delete icon, confirm via dialog |
| 2.13 | Delete confirm dialog | `AlertDialog` | Shows character name/race/class, "Удалить" and "Отмена" |
| 2.14 | Inventory sub-card | `Card` + `InkWell` | "🎒 Инвентарь [name]", shows item count or "Пусто" |
| 2.15 | "✨ Полное создание (визард)" | `ElevatedButton.icon` | Navigates to `/character_wizard` |
| 2.16 | "Быстрое создание" | `OutlinedButton.icon` | Navigates to `/character_create` |

### State Behavior
- **Loading:** Centered spinner
- **Empty:** Empty state with icon, text, and create buttons
- **With characters:** Scrolling list of character cards with inventory sub-cards, plus create section at bottom
- **Logged out:** Listen on `authProvider` → auto-redirect to `/login`

### API Calls
| Action | Endpoint | Method |
|---|---|---|
| List characters | `GET /api/v1/characters` | `_get` |
| Delete character | `DELETE /api/v1/characters/{id}` | `_delete` |

### Error States to Test
- [ ] Network error during load → `_chars` stays empty, "У вас пока нет персонажей" shown (error swallowed)
- [ ] Delete fails → SnackBar with "Ошибка: ..."
- [ ] User cancels delete dialog → character not removed
- [ ] Delete succeeds → character removed from list
- [ ] Swipe gesture → only red background + confirm, not accidental deletion
- [ ] After character_create returns `true` → list refreshes
- [ ] After character_wizard returns `true` → list refreshes
- [ ] Logout → clears token, redirects to `/login`

---

## 3. Character Create Screen (`character_create_screen.dart`) — Route: `/character_create`

### Widgets
| # | Widget | Type | Expected Behavior |
|---|---|---|---|
| 3.1 | AppBar title | `Text` | "Новый персонаж" |
| 3.2 | Name field | `TextField` | Parchment, 20pt, label "Имя", hint "Введите имя персонажа" |
| 3.3 | Race dropdown | `DropdownButtonFormField` | 9 races: Человек, Эльф, Дварф, Полурослик, Драконорождённый, Тифлинг, Полуэльф, Полуорк, Гном |
| 3.4 | Class dropdown | `DropdownButtonFormField` | 12 classes: Воин, Волшебник, Плут, Жрец, Следопыт, Паладин, Варвар, Бард, Друид, Колдун, Чародей, Монах |
| 3.5 | Level slider | `Slider` | 1–20, gold color, shows current level |
| 3.6 | Point Buy counter | `Text` | Shows "Очки характеристик: N / 27", green when 0, red when negative |
| 3.7 | "Стандартный массив" button | `TextButton.icon` | Applies 15,14,13,12,10,8 |
| 3.8 | Warning text | `Text` (conditional) | "⚠ Превышен лимит очков!" when `remaining < 0` |
| 3.9 | Stat rows (×6) | Row with IconButtons | Each row: label, − button, base value, + button, final value+badge, modifier, cost |
| 3.10 | Create button | `ElevatedButton` | Shows HP/AC preview. Disabled if points not OK. Shows spinner while saving. |

### Point Buy Rules
- Base: 8, Max pre-racial: 15, Total points: 27
- Costs: 8→0, 9→1, 10→2, 11→3, 12→4, 13→5, 14→7, 15→9
- Racial bonuses applied after point buy (e.g., Человек gets +1 all, Эльф +2 dex)

### Validation
- Name must not be empty → SnackBar "Введите имя персонажа"
- All 27 points must be spent → SnackBar with remaining count
- Both conditions must pass before API call

### API Calls (3-step process)
| Step | Endpoint | Method | Body |
|---|---|---|---|
| 1. Create draft | `POST /api/v1/characters/create` | `_post` | `{name, race, class_name}` |
| 2. Set stats | `POST /api/v1/characters/{id}/stats` | `_post` | `{stats, skill_proficiencies:[], languages:[]}` |
| 3. Finalize | `POST /api/v1/characters/{id}/finalize?background_name=` | `_post` | `{backstory: ''}` |

### Error States to Test
- [ ] Empty name → SnackBar, no API call
- [ ] Points not fully spent → SnackBar, no API call
- [ ] Points overspent → Create button disabled, red warning shown
- [ ] API fails at step 1 (create draft) → SnackBar "Ошибка: ...", saving=false
- [ ] API fails at step 2 (set stats) → SnackBar, but draft already created (orphan)
- [ ] API fails at step 3 (finalize) → SnackBar, character partially created
- [ ] Network timeout mid-creation → error shown
- [ ] Rapid double-tap → `_saving` flag prevents duplicate calls
- [ ] Minus button grayed out when stat at 8
- [ ] Plus button grayed out when stat at 15 or not enough points
- [ ] Racial bonus displayed correctly when race changes
- [ ] Standard array works and uses exactly 27 points
- [ ] HP/AC preview updates when stats change

---

## 4. Character Wizard Screen (`character_wizard_screen.dart`) — Route: `/character_wizard`

### 6-Step Wizard (PageView, non-scrollable)

**Step indicator:** Horizontal bar at top of AppBar, 6 segments. Gold = current, faded = done, gray = future.

**Navigation:** "Назад" button (hidden on step 0) + "Далее →" / "✨ Завершить" button

### Step 0: Name
| Widget | Expected Behavior |
|---|---|
| Person icon | Gold, 64px |
| "Как зовут твоего героя?" | Headline text |
| Name TextField | Autofocus, 28pt, centered, underlined |
| Validation hint | "Минимум 2 символа" in red if length < 2 and > 0 |
| **Next enabled:** name.length >= 2 |

### Step 1: Race & Class
| Widget | Expected Behavior |
|---|---|
| "Выбери расу" header | Gold, 18pt |
| Race cards | From `GET /api/v1/srd/races`. Selected = gold border+bg, shows elf icon, name, description, traits |
| Race info button (ℹ️) | Opens `showModalBottomSheet` with full race details + traits |
| "Выбери класс" header | Gold, 18pt |
| Class cards | From `GET /api/v1/srd/classes`. Shows sword icon, name, description, hit die |
| Class info button (ℹ️) | Opens `showModalBottomSheet` with class features, proficiencies |
| Racial bonus chips | Shows stat bonuses for selected race (e.g., "+2 ЛОВ") |
| **Next enabled:** both race and class selected |
| **Next action:** Calls `createDraft` API |

### Step 2: Stats (Point Buy)
| Widget | Expected Behavior |
|---|---|
| Points counter | "Очки: N / 27", green at 0, red when negative |
| "Массив" button | Applies standard array |
| 6 stat rows | Each: emoji icon, label, −/+ buttons, base value, arrow, final value with racial bonus, modifier, cost |
| **Next enabled:** points spent == 27 |
| **Next action:** Calls `setStats` API + saves skills/languages |

### Step 3: Skills & Languages
| Widget | Expected Behavior |
|---|---|
| "Выбери N навыка(ов) (ClassName)" | Gold header |
| Selection count | "Выбрано: X/N" |
| Skill cards | From class's `skills_choices.from`. Tappable toggle. Info button shows skill description |
| "Языки" section | Chosen languages shown as deletable chips |
| Standard languages | FilterChips for 10 D&D standard languages |
| Exotic languages | FilterChips for 7 exotic languages |
| Custom language input | TextField + add button for custom languages |
| **Next enabled:** chosen skills >= skillsToPick |
| **Next action:** Goes to spells (caster) or jumps to background (non-caster) |

### Step 4: Spells (Casters Only — auto-skipped for non-casters)
| Widget | Expected Behavior |
|---|---|
| "✨ Выбери заклинания" | Header with casting ability |
| Spell slots chips | Shows slot counts per level |
| Cantrip/spell counters | "Заговоры: X / N    Заклинания: X / N" |
| Spell cards grouped by level | Tappable toggle. Dimmed (35% opacity) when at limit. Info button shows spell detail |
| Spell detail sheet | Shows name, school, description, flavor |
| **Auto-skip:** Non-casters jump directly from step 3 → step 5 (background) |
| **Next enabled:** always (spells optional) |

### Step 5: Background & Backstory
| Widget | Expected Behavior |
|---|---|
| "Предыстория" header | Gold, 18pt |
| Background cards | From `GET /api/v1/srd/backgrounds`. Shows name, feature description, skills. Selectable. |
| "История персонажа" header | Gold, 18pt |
| Backstory TextField | 6 lines, hint "Эльфийский следопыт, выросший в лесах..." |
| Hint text | "Минимум 10 слов" |
| **Next (final) enabled:** background selected |
| **Final action:** Calls `finalizeCharacter` + `addSpell` for each chosen spell |

### API Calls
| Action | Endpoint | Method |
|---|---|---|
| Load SRD races | `GET /api/v1/srd/races` | `_get` |
| Load SRD classes | `GET /api/v1/srd/classes` | `_get` |
| Load SRD backgrounds | `GET /api/v1/srd/backgrounds` | `_get` |
| Create draft | `POST /api/v1/characters/create` | `_post` |
| Set stats | `POST /api/v1/characters/{id}/stats` | `_post` |
| Finalize | `POST /api/v1/characters/{id}/finalize?background_name=X` | `_post` |
| Add spell (per spell) | `POST /api/v1/characters/{id}/spells` | `_post` |

### Error States to Test
- [ ] SRD data fails to load → races/classes/backgrounds lists empty, cards not shown
- [ ] Name < 2 chars → "Далее" disabled, red hint shown
- [ ] No race selected → "Далее" disabled on step 1
- [ ] No class selected → "Далее" disabled on step 1
- [ ] Create draft API fails → SnackBar error, stays on step 1, `_charId` remains null
- [ ] Points != 27 → "Далее" disabled on step 2
- [ ] setStats API fails → SnackBar, stays on step 2/3
- [ ] Not enough skills selected → "Далее" disabled on step 3
- [ ] Spell limit reached → unselected spells dimmed, untappable
- [ ] Non-caster correctly skips spell step → `_pageCtrl.jumpToPage(5)`
- [ ] Finalize API fails → SnackBar, stays on step 5
- [ ] addSpell fails for individual spells → swallowed (`catch (_) {}`), other spells still saved
- [ ] Back button works correctly through all steps
- [ ] Network error during SRD load → empty state, SnackBar not shown
- [ ] "Назад" from step 1 works (goes to step 0 without API call)

---

## 5. Chat Screen (`chat_screen.dart`) — Route: `/chat`

### Widgets
| # | Widget | Type | Expected Behavior |
|---|---|---|---|
| 5.1 | Back button | `IconButton(Icons.arrow_back)` | Navigates to `/characters` (replace) |
| 5.2 | AppBar title | `Text` | "D&D AI Master" |
| 5.3 | Character subtitle | `Text` | "{name} — {race} {class} lvl {level} | HP: X/Y" (gold, 11pt) |
| 5.4 | Status button | `IconButton(Icons.bar_chart_rounded)` | Navigates to `/status` with characterId, characterName |
| 5.5 | Dice roller button | `DiceRoller` widget | Opens dice dialog |
| 5.6 | Clear chat button | `IconButton(Icons.delete_outline)` | Opens clear confirmation dialog |
| 5.7 | Error banner | `MaterialBanner` | Red bg, shows error text, "ЗАКРЫТЬ" button |
| 5.8 | Empty state | Centered column | Book icon (80px), "Начните своё приключение...", hint text |
| 5.9 | Message list | `ListView.builder` | Scrollable, auto-scrolls to bottom on new message |
| 5.10 | Typing indicator | `TypingIndicator` | "Мастер пишет" with animated dots |
| 5.11 | Chat input | `ChatInput` widget | See below |

### ChatInput Widget
| Widget | Expected Behavior |
|---|---|
| TextField | Multi-line (1–5), "Опишите ваше действие..." hint, disabled when loading |
| Send button | Gold send icon or spinner when loading |
| Keyboard submit | Triggers send on `TextInputAction.send` |

### ChatMessageTile Widget
| Role | Appearance |
|---|---|
| `user` | Right-aligned, leather bg, gold border, plain text |
| `assistant` | Left-aligned, dark brown bg, leather border, Markdown rendered |
| `system` | Centered, black bg, gold border, Markdown (dice results) |
| Roll request button | Shown when assistant message contains dice roll pattern, "Бросить dN" |

### DiceRoller Dialog
| Widget | Expected Behavior |
|---|---|
| Label TextField | "Название (опционально)", sets roll label |
| Modifier buttons | −/+ to adjust modifier |
| Dice buttons | d4, d6, d8, d10, d12, d20, d100 — gold ElevatedButtons |
| Each button tap | Rolls dice, sends to server if character selected, closes dialog |

### Clear Dialog
- "Очистить чат?" title
- Warning: "История будет удалена на устройстве И на сервере"
- "ОТМЕНА" closes dialog, "ОЧИСТИТЬ" (red) clears everything

### API Calls
| Action | Endpoint | Method | Body |
|---|---|---|---|
| Send message | `POST /api/v1/chat` | `_post` | `{user_id, message, character_id?, dice_roll?}` |
| Clear history | `DELETE /api/v1/chat/history/{userId}` | `_delete` | — |

### Chat Provider Logic
- Messages persisted to local storage (`storage_service.dart`)
- User ID generated via UUID (persisted to storage)
- `sendMessage`: adds user message → sets loading → calls API → adds assistant reply
- `rollDice`: rolls locally, adds system message, sends to server with DiceRollData
- `clearChat`: clears server history + local storage, generates new userId
- `clearError`: dismisses error banner

### Error States to Test
- [ ] Send empty message → nothing happens
- [ ] Send while loading → nothing happens (early return)
- [ ] Network error during send → error banner shows, user message stays
- [ ] `ChatApiException` → error banner with message
- [ ] Generic exception → error banner "Ошибка: ..."
- [ ] Dismiss error → banner removed
- [ ] Clear chat confirm → history cleared, new userId generated
- [ ] Clear chat cancel → nothing happens
- [ ] Dice roll without character → local only, no server call
- [ ] Dice roll with character → sends to server, assistant reply added
- [ ] No character selected → character subtitle hidden, status button hidden
- [ ] Storage init fails → fallback to UUID, messages empty
- [ ] Message persistence fails → swallowed, chat continues
- [ ] Long messages → Markdown rendering, multiline display
- [ ] Roll request parsing → button shown for messages containing dice patterns
- [ ] Typing indicator visible during loading
- [ ] Auto-scroll on new messages
- [ ] Back button navigates correctly

---

## 6. Status Screen (`status_screen.dart`) — Route: `/status`

### Parameters: `characterId`, `characterName`

### 3 Tabs: Статы | Заклинания | Навыки

### Tab 1: Статы (Stats)
| Widget | Expected Behavior |
|---|---|
| Character header card | Level avatar, name, race+class, HP, AC, speed, prof bonus |
| Spell attack info (casters only) | "🎯 Атака закл: +N | Сл: N (INT/WIS/CHA)" |
| 6 stat rows | Icon label, value in box, modifier (green ≥14, red ≤9), save bonus |
| Features list | `ListTile` with auto_awesome icon, name, description |
| Feature tap | Opens modal bottom sheet with full feature details |
| Backstory | Styled container with backstory text |
| Languages | Chips list or "Не выбраны" |

### Tab 2: Заклинания (Spells)
| Widget | Expected Behavior |
|---|---|
| Empty state | "Нет заклинаний" with icon and "Спроси DM найти свиток!" hint |
| Spell slots chips | Per-level slot display |
| Spells grouped by level | Level header + spell tiles |
| Spell tile | Colored dot (by school), name, school·casting·range, flavor text |
| Spell tap | Opens modal bottom sheet with full spell details |
| School colors | Воплощение=red, Ограждение=blue, Прорицание=purple, Очарование=pink, Иллюзия=teal, Некромантия=gray, Преобразование=orange |

### Tab 3: Навыки (Skills)
| Widget | Expected Behavior |
|---|---|
| Prof bonus display | "Бонус мастерства: +N" |
| Skill rows | Name, stat icon, stat abbreviation, bonus in box |
| Proficient skills | Gold dot, gold border+bg, highlighted bonus |
| Skill tap | Opens modal with skill name, stat, bonus, proficiency status, flavor |
| Languages section | Same as stats tab |

### API Calls
| Action | Endpoint | Method |
|---|---|---|
| Get status | `GET /api/v1/characters/{id}/status` | `_get` |

### Error States to Test
- [ ] API fails → `_status` stays null, "Ошибка загрузки" shown
- [ ] Network timeout → spinner stays then error
- [ ] Empty spells list → empty state with hint
- [ ] No features → features section hidden
- [ ] No backstory → backstory section hidden
- [ ] No languages → "Не выбраны"
- [ ] Non-caster → no spell attack info, no spells
- [ ] Tab switching → content updates correctly
- [ ] Skill detail sheet → shows flavor text if available
- [ ] Spell detail sheet → shows all spell properties
- [ ] Feature detail sheet → shows name, desc, source

---

## 7. Inventory Screen (`inventory_screen.dart`) — Route: `/inventory`

### Parameters: `characterId`, `characterName`, `preloadedItems` (optional)

### Widgets
| # | Widget | Type | Expected Behavior |
|---|---|---|---|
| 7.1 | AppBar title | `Text` | "🎒 Инвентарь {characterName}" |
| 7.2 | Loading spinner | `CircularProgressIndicator` | Gold, centered |
| 7.3 | Error state | Column with icon, text, retry button | Red error icon, message, "Повторить" gold button |
| 7.4 | Empty state | Centered column | Backpack icon (64px), "Инвентарь пуст", hint text |
| 7.5 | Pull-to-refresh | `RefreshIndicator` | Swipe down to reload |
| 7.6 | Grouped item list | `ListView` with sections | Items grouped by type with headers |
| 7.7 | Type headers | Row with icon + count | e.g., "⚔️ Оружие (3)" |
| 7.8 | Item card | `ListTile` in `Card` | Type icon, item name, subtitle (flavor or subtype×qty) |
| 7.9 | Delete button | `IconButton(Icons.delete_outline)` | Red, per item |
| 7.10 | Delete confirm dialog | `AlertDialog` | "Удалить предмет?", item name shown |
| 7.11 | Item detail sheet | `showModalBottomSheet` | Shows icon, name, subtype/qty/equipped/attunement chips, flavor, slot, modifiers, notes |

### Item Type Order & Icons
| Type | Icon | Label |
|---|---|---|
| weapon | `Icons.gavel` | ⚔️ Оружие |
| armor | `Icons.shield` | 🛡️ Броня |
| shield | `Icons.shield` | 🛡️ Щиты |
| focus | `Icons.auto_awesome` | ✨ Фокусы |
| potion | `Icons.local_drink` | 🧪 Зелья |
| ammo | `Icons.sports_martial_arts` | 🏹 Боеприпасы |
| gear | `Icons.backpack` | 🎒 Снаряжение |
| tool | `Icons.build` | 🔧 Инструменты |
| other | `Icons.category` | Raw type name |

### API Calls
| Action | Endpoint | Method |
|---|---|---|
| List items (if no preload) | `GET /api/v1/characters/{id}/items` | `_get` |
| Remove item | `DELETE /api/v1/characters/{id}/items/{itemId}` | `_delete` |

### Error States to Test
- [ ] Preloaded items → no API call, immediately shows items
- [ ] No preloaded items → API call on init
- [ ] API fails → error state with retry button
- [ ] Retry button → calls `_load()` again
- [ ] Pull-to-refresh → calls `_load()`
- [ ] Delete confirm cancel → item not removed
- [ ] Delete API fails → SnackBar with error
- [ ] Delete success → list refreshes
- [ ] Empty list → empty state shown
- [ ] Item detail sheet → all metadata displayed
- [ ] Items with flavor → flavor shown as subtitle
- [ ] Items without flavor → subtype × qty shown
- [ ] Equipped/attunement chips shown in detail
- [ ] Modifiers displayed in detail
- [ ] Notes displayed in detail with divider
- [ ] Custom slot shown in detail

---

## 8. Cross-Screen Flows to Test

### Authentication Flow
- [ ] Fresh app launch → `/login` shown
- [ ] Register new user → auto-login, redirect to `/characters`
- [ ] Login existing user → redirect to `/characters`
- [ ] Logout from character screen → redirect to `/login`
- [ ] Direct navigation to protected route while logged out → redirect to `/login`
- [ ] Back button from `/characters` while logged in → should not go to `/login`

### Character Creation Flow
- [ ] Quick create: `/characters` → `/character_create` → fill form → save → pop back → list refreshed
- [ ] Wizard: `/characters` → `/character_wizard` → complete all 6 steps → pop back → list refreshed
- [ ] Cancel/back from create screens → character list unchanged

### Chat Flow
- [ ] Select character → navigate to `/chat` → character info in AppBar
- [ ] Send message → user bubble appears → typing indicator → assistant reply
- [ ] Dice roll from toolbar → dialog → select dice → system message → assistant reply
- [ ] Dice roll from message (roll request button) → auto-roll with parsed params
- [ ] Error mid-conversation → error banner → dismiss → continue
- [ ] Clear chat → confirm → empty state → new messages
- [ ] Status button → `/status` tabbed view → back to chat
- [ ] Back from chat → character list

### Inventory Flow
- [ ] Character screen → tap inventory card → `/inventory` with preloaded items
- [ ] View item details → bottom sheet
- [ ] Delete item → confirm → removal
- [ ] Pull-to-refresh → updated list
- [ ] Back → character screen

### Status Flow
- [ ] Chat → tap status icon → `/status` → 3 tabs
- [ ] Switch tabs → content updates
- [ ] Tap spell/skill/feature → detail sheet
- [ ] Back → chat

---

## 9. Global Error States

| Scenario | Expected |
|---|---|
| No network (any API call) | `ChatApiException('Нет связи с сервером.')` → SnackBar or error display |
| Server timeout (15s connect, request timeout) | `ChatApiException('Сервер не ответил вовремя.')` |
| Server 4xx/5xx | `ChatApiException('detail' \|\| 'Ошибка NNN')` |
| ClientException retry | Auto-retries once on connection death |
| Empty API response | Empty map returned, screen shows empty/error state |
| Rapid navigation | No crashes, no duplicate routes |
| Screen rotation | Layout adapts, no state loss |
| App background/foreground | State preserved, no crashes |

---

## 10. Edge Cases & Special Scenarios

### Login Screen
- [ ] Very long username/password → no overflow
- [ ] Special characters in credentials → handled by API
- [ ] Toggle login↔register preserves field values
- [ ] Keyboard dismiss on submit

### Character Screen
- [ ] Many characters → scrolling performance
- [ ] Character with no items → "Пусто" shown
- [ ] Character with many items → "..." truncation at 4 items
- [ ] Stat modifier calculation: (stat - 10) ~/ 2

### Character Create
- [ ] Change race → racial bonuses update immediately in stat rows
- [ ] Change class → no effect on stats
- [ ] Point Buy edge: cannot go below 8 or above 15
- [ ] Spend exactly 27 points → button enabled, counter green
- [ ] 0 points remaining at exactly 27 → valid
- [ ] Negative remaining → button disabled

### Character Wizard
- [ ] SRD data fails silently → empty lists, user sees no cards
- [ ] Non-caster spell step skip → jumpToPage(5) works
- [ ] Skill count varies by class → skillsToPick updates
- [ ] All skills selected → remaining cards untappable
- [ ] Custom language → adds to chosenLanguages
- [ ] 0 cantrips / 0 level 1 spells allowed → all spells dimmed

### Chat
- [ ] Very long messages → multi-line bubbles
- [ ] Markdown in assistant messages → rendered correctly
- [ ] Mixed content (bold, italic, lists, code blocks) → all rendered
- [ ] Rapid sending → disabled during loading
- [ ] Storage corrupted → fallback to new UUID
- [ ] Empty messages list → empty state, not scrollable

### Status
- [ ] Level 1 character (no prof bonus) → shows correctly
- [ ] Multi-class spells → all shown
- [ ] Skills with flavor text → shown in detail
- [ ] Features with source → shown in detail
- [ ] Empty languages array → "Не выбраны"

### Inventory
- [ ] Very many items → scrolling performance
- [ ] Item with all metadata (modifiers, notes, flavor, slot, equipped, attunement) → full detail sheet
- [ ] Unknown item type → `Icons.category`, raw type name
- [ ] Preloaded items from character screen → no loading spinner
