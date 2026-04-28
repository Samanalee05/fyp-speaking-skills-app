class AnalysisResult {
  final int? id;
  final String createdAt;
  final String mode;
  final String inputType;
  final String? audioPath;

  final String status;
  final String authenticityLabel;
  final double authenticityConfidence;

  final String overallLevel;
  final String fluencyLevel;
  final String expressivenessLevel;

  final double? speechDuration;
  final double? speakingRate;
  final int? pauseCount;

  final String feedbackSummary;
  final String rawJson;

  const AnalysisResult({
    this.id,
    required this.createdAt,
    required this.mode,
    required this.inputType,
    this.audioPath,
    required this.status,
    required this.authenticityLabel,
    required this.authenticityConfidence,
    required this.overallLevel,
    required this.fluencyLevel,
    required this.expressivenessLevel,
    this.speechDuration,
    this.speakingRate,
    this.pauseCount,
    required this.feedbackSummary,
    required this.rawJson,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'created_at': createdAt,
      'mode': mode,
      'input_type': inputType,
      'audio_path': audioPath,
      'status': status,
      'authenticity_label': authenticityLabel,
      'authenticity_confidence': authenticityConfidence,
      'overall_level': overallLevel,
      'fluency_level': fluencyLevel,
      'expressiveness_level': expressivenessLevel,
      'speech_duration': speechDuration,
      'speaking_rate': speakingRate,
      'pause_count': pauseCount,
      'feedback_summary': feedbackSummary,
      'raw_json': rawJson,
    };
  }

  factory AnalysisResult.fromMap(Map<String, dynamic> map) {
    return AnalysisResult(
      id: map['id'] as int?,
      createdAt: map['created_at'] as String,
      mode: map['mode'] as String,
      inputType: map['input_type'] as String,
      audioPath: map['audio_path'] as String?,
      status: map['status'] as String,
      authenticityLabel: map['authenticity_label'] as String,
      authenticityConfidence: (map['authenticity_confidence'] as num).toDouble(),
      overallLevel: map['overall_level'] as String,
      fluencyLevel: map['fluency_level'] as String,
      expressivenessLevel: map['expressiveness_level'] as String,
      speechDuration: (map['speech_duration'] as num?)?.toDouble(),
      speakingRate: (map['speaking_rate'] as num?)?.toDouble(),
      pauseCount: map['pause_count'] as int?,
      feedbackSummary: map['feedback_summary'] as String,
      rawJson: map['raw_json'] as String,
    );
  }
}