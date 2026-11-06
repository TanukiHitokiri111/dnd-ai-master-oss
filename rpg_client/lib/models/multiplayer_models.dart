/// Модели для мультиплеера: сессии, друзья, игровые сообщения.

class SessionMember {
  final int id;
  final String userId;
  final String? characterId;
  final String role;
  final int? initiative;
  final int turnOrder;
  final bool isReady;
  final String username;
  final String? characterName;
  final Map<String, dynamic>? characterStats;

  const SessionMember({
    required this.id, required this.userId, this.characterId,
    required this.role, this.initiative, required this.turnOrder,
    required this.isReady, required this.username, this.characterName,
    this.characterStats,
  });

  factory SessionMember.fromJson(Map<String, dynamic> j) => SessionMember(
    id: j['id'] ?? 0, userId: j['user_id'] ?? '',
    characterId: j['character_id'],
    role: j['role'] ?? 'player', initiative: j['initiative'],
    turnOrder: j['turn_order'] ?? 0,
    isReady: j['is_ready'] == true || j['is_ready'] == 1,
    username: j['username'] ?? '???',
    characterName: j['character_name'],
    characterStats: j['character_stats'] is Map ? Map<String,dynamic>.from(j['character_stats']) : null,
  );
}

class SessionData {
  final String id, name, ownerId, inviteCode, state;
  final int turnIndex;
  final String createdAt;
  final List<SessionMember> members;
  final String? currentTurnUserId;

  const SessionData({
    required this.id, required this.name, required this.ownerId,
    required this.inviteCode, required this.state, required this.turnIndex,
    required this.createdAt, required this.members, this.currentTurnUserId,
  });

  factory SessionData.fromJson(Map<String, dynamic> j) => SessionData(
    id: j['id']?.toString() ?? '', name: j['name'] ?? '',
    ownerId: j['owner_id'] ?? '', inviteCode: j['invite_code'] ?? '',
    state: j['state'] ?? 'lobby', turnIndex: j['turn_index'] ?? 0,
    createdAt: j['created_at'] ?? '',
    members: ((j['members'] as List?) ?? [])
        .where((m) => m is Map<String, dynamic>)
        .map((m) => SessionMember.fromJson(m as Map<String, dynamic>))
        .toList(),
    currentTurnUserId: j['current_turn_user_id'],
  );

  bool isOwner(String uid) => ownerId == uid;
  bool get isLobby => state == 'lobby';
  bool get isPlaying => state == 'playing';
}

class FriendData {
  final String userId, username, status;
  final String createdAt;
  final int? requestId; // для pending запросов

  const FriendData({
    required this.userId, required this.username,
    required this.status, this.createdAt = '', this.requestId,
  });

  factory FriendData.fromJson(Map<String, dynamic> j) => FriendData(
    userId: j['user_id'] ?? '', username: j['username'] ?? '',
    status: j['status'] ?? 'accepted', createdAt: j['created_at'] ?? '',
    requestId: j['id'] is int ? j['id'] : null,
  );
}

class GameMessage {
  final int id;
  final String userId, role, content;
  final String? characterId;
  final Map<String, dynamic>? diceRoll;
  final String createdAt;

  const GameMessage({
    required this.id, required this.userId, required this.role,
    required this.content, this.characterId, this.diceRoll,
    required this.createdAt,
  });

  factory GameMessage.fromJson(Map<String, dynamic> j) => GameMessage(
    id: j['id'] ?? 0, userId: j['user_id'] ?? '',
    role: j['role'] ?? 'user', content: j['content'] ?? '',
    characterId: j['character_id'],
    diceRoll: j['dice_roll'] is Map ? Map<String,dynamic>.from(j['dice_roll']) : null,
    createdAt: j['created_at'] ?? '',
  );
}
