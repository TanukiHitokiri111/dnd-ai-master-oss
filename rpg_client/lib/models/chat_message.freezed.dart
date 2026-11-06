// coverage:ignore-file
// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'chat_message.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

T _$identity<T>(T value) => value;

final _privateConstructorUsedError = UnsupportedError(
    'It seems like you constructed your class using `MyClass._()`. This constructor is only meant to be used by freezed and you are not supposed to need it nor use it.\nPlease check the documentation here for more information: https://github.com/rrousselGit/freezed#adding-getters-and-methods-to-our-models');

ChatMessage _$ChatMessageFromJson(Map<String, dynamic> json) {
  return _ChatMessage.fromJson(json);
}

/// @nodoc
mixin _$ChatMessage {
  String get id => throw _privateConstructorUsedError;
  String get role => throw _privateConstructorUsedError;
  String get content => throw _privateConstructorUsedError;
  bool get isMarkdown => throw _privateConstructorUsedError;
  bool get streaming => throw _privateConstructorUsedError;
  DateTime? get timestamp => throw _privateConstructorUsedError;
  String? get imageUrl => throw _privateConstructorUsedError;
  String? get appearanceUrl => throw _privateConstructorUsedError;
  String? get npcUrl => throw _privateConstructorUsedError;
  String? get npcName => throw _privateConstructorUsedError;

  /// Serializes this ChatMessage to a JSON map.
  Map<String, dynamic> toJson() => throw _privateConstructorUsedError;

  /// Create a copy of ChatMessage
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  $ChatMessageCopyWith<ChatMessage> get copyWith =>
      throw _privateConstructorUsedError;
}

/// @nodoc
abstract class $ChatMessageCopyWith<$Res> {
  factory $ChatMessageCopyWith(
          ChatMessage value, $Res Function(ChatMessage) then) =
      _$ChatMessageCopyWithImpl<$Res, ChatMessage>;
  @useResult
  $Res call(
      {String id,
      String role,
      String content,
      bool isMarkdown,
      bool streaming,
      DateTime? timestamp,
      String? imageUrl,
      String? appearanceUrl,
      String? npcUrl,
      String? npcName});
}

/// @nodoc
class _$ChatMessageCopyWithImpl<$Res, $Val extends ChatMessage>
    implements $ChatMessageCopyWith<$Res> {
  _$ChatMessageCopyWithImpl(this._value, this._then);

  // ignore: unused_field
  final $Val _value;
  // ignore: unused_field
  final $Res Function($Val) _then;

  /// Create a copy of ChatMessage
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? role = null,
    Object? content = null,
    Object? isMarkdown = null,
    Object? streaming = null,
    Object? timestamp = freezed,
    Object? imageUrl = freezed,
    Object? appearanceUrl = freezed,
    Object? npcUrl = freezed,
    Object? npcName = freezed,
  }) {
    return _then(_value.copyWith(
      id: null == id
          ? _value.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _value.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      content: null == content
          ? _value.content
          : content // ignore: cast_nullable_to_non_nullable
              as String,
      isMarkdown: null == isMarkdown
          ? _value.isMarkdown
          : isMarkdown // ignore: cast_nullable_to_non_nullable
              as bool,
      streaming: null == streaming
          ? _value.streaming
          : streaming // ignore: cast_nullable_to_non_nullable
              as bool,
      timestamp: freezed == timestamp
          ? _value.timestamp
          : timestamp // ignore: cast_nullable_to_non_nullable
              as DateTime?,
      imageUrl: freezed == imageUrl
          ? _value.imageUrl
          : imageUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      appearanceUrl: freezed == appearanceUrl
          ? _value.appearanceUrl
          : appearanceUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      npcUrl: freezed == npcUrl
          ? _value.npcUrl
          : npcUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      npcName: freezed == npcName
          ? _value.npcName
          : npcName // ignore: cast_nullable_to_non_nullable
              as String?,
    ) as $Val);
  }
}

/// @nodoc
abstract class _$$ChatMessageImplCopyWith<$Res>
    implements $ChatMessageCopyWith<$Res> {
  factory _$$ChatMessageImplCopyWith(
          _$ChatMessageImpl value, $Res Function(_$ChatMessageImpl) then) =
      __$$ChatMessageImplCopyWithImpl<$Res>;
  @override
  @useResult
  $Res call(
      {String id,
      String role,
      String content,
      bool isMarkdown,
      bool streaming,
      DateTime? timestamp,
      String? imageUrl,
      String? appearanceUrl,
      String? npcUrl,
      String? npcName});
}

/// @nodoc
class __$$ChatMessageImplCopyWithImpl<$Res>
    extends _$ChatMessageCopyWithImpl<$Res, _$ChatMessageImpl>
    implements _$$ChatMessageImplCopyWith<$Res> {
  __$$ChatMessageImplCopyWithImpl(
      _$ChatMessageImpl _value, $Res Function(_$ChatMessageImpl) _then)
      : super(_value, _then);

  /// Create a copy of ChatMessage
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? role = null,
    Object? content = null,
    Object? isMarkdown = null,
    Object? streaming = null,
    Object? timestamp = freezed,
    Object? imageUrl = freezed,
    Object? appearanceUrl = freezed,
    Object? npcUrl = freezed,
    Object? npcName = freezed,
  }) {
    return _then(_$ChatMessageImpl(
      id: null == id
          ? _value.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _value.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      content: null == content
          ? _value.content
          : content // ignore: cast_nullable_to_non_nullable
              as String,
      isMarkdown: null == isMarkdown
          ? _value.isMarkdown
          : isMarkdown // ignore: cast_nullable_to_non_nullable
              as bool,
      streaming: null == streaming
          ? _value.streaming
          : streaming // ignore: cast_nullable_to_non_nullable
              as bool,
      timestamp: freezed == timestamp
          ? _value.timestamp
          : timestamp // ignore: cast_nullable_to_non_nullable
              as DateTime?,
      imageUrl: freezed == imageUrl
          ? _value.imageUrl
          : imageUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      appearanceUrl: freezed == appearanceUrl
          ? _value.appearanceUrl
          : appearanceUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      npcUrl: freezed == npcUrl
          ? _value.npcUrl
          : npcUrl // ignore: cast_nullable_to_non_nullable
              as String?,
      npcName: freezed == npcName
          ? _value.npcName
          : npcName // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
@JsonSerializable()
class _$ChatMessageImpl implements _ChatMessage {
  const _$ChatMessageImpl(
      {required this.id,
      required this.role,
      required this.content,
      this.isMarkdown = false,
      this.streaming = false,
      this.timestamp,
      this.imageUrl,
      this.appearanceUrl,
      this.npcUrl,
      this.npcName});

  factory _$ChatMessageImpl.fromJson(Map<String, dynamic> json) =>
      _$$ChatMessageImplFromJson(json);

  @override
  final String id;
  @override
  final String role;
  @override
  final String content;
  @override
  @JsonKey()
  final bool isMarkdown;
  @override
  @JsonKey()
  final bool streaming;
  @override
  final DateTime? timestamp;
  @override
  final String? imageUrl;
  @override
  final String? appearanceUrl;
  @override
  final String? npcUrl;
  @override
  final String? npcName;

  @override
  String toString() {
    return 'ChatMessage(id: $id, role: $role, content: $content, isMarkdown: $isMarkdown, streaming: $streaming, timestamp: $timestamp, imageUrl: $imageUrl, appearanceUrl: $appearanceUrl, npcUrl: $npcUrl, npcName: $npcName)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _$ChatMessageImpl &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.role, role) || other.role == role) &&
            (identical(other.content, content) || other.content == content) &&
            (identical(other.isMarkdown, isMarkdown) ||
                other.isMarkdown == isMarkdown) &&
            (identical(other.streaming, streaming) ||
                other.streaming == streaming) &&
            (identical(other.timestamp, timestamp) ||
                other.timestamp == timestamp) &&
            (identical(other.imageUrl, imageUrl) ||
                other.imageUrl == imageUrl) &&
            (identical(other.appearanceUrl, appearanceUrl) ||
                other.appearanceUrl == appearanceUrl) &&
            (identical(other.npcUrl, npcUrl) || other.npcUrl == npcUrl) &&
            (identical(other.npcName, npcName) || other.npcName == npcName));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, role, content, isMarkdown,
      streaming, timestamp, imageUrl, appearanceUrl, npcUrl, npcName);

  /// Create a copy of ChatMessage
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  @pragma('vm:prefer-inline')
  _$$ChatMessageImplCopyWith<_$ChatMessageImpl> get copyWith =>
      __$$ChatMessageImplCopyWithImpl<_$ChatMessageImpl>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$$ChatMessageImplToJson(
      this,
    );
  }
}

abstract class _ChatMessage implements ChatMessage {
  const factory _ChatMessage(
      {required final String id,
      required final String role,
      required final String content,
      final bool isMarkdown,
      final bool streaming,
      final DateTime? timestamp,
      final String? imageUrl,
      final String? appearanceUrl,
      final String? npcUrl,
      final String? npcName}) = _$ChatMessageImpl;

  factory _ChatMessage.fromJson(Map<String, dynamic> json) =
      _$ChatMessageImpl.fromJson;

  @override
  String get id;
  @override
  String get role;
  @override
  String get content;
  @override
  bool get isMarkdown;
  @override
  bool get streaming;
  @override
  DateTime? get timestamp;
  @override
  String? get imageUrl;
  @override
  String? get appearanceUrl;
  @override
  String? get npcUrl;
  @override
  String? get npcName;

  /// Create a copy of ChatMessage
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  _$$ChatMessageImplCopyWith<_$ChatMessageImpl> get copyWith =>
      throw _privateConstructorUsedError;
}
