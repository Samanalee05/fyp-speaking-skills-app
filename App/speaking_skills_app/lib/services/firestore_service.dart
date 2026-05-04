import 'dart:convert';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class FirestoreService {
  final _db = FirebaseFirestore.instance;
  final _auth = FirebaseAuth.instance;

  Future<void> saveAnalysisFromResponse({
    required Map<String, dynamic> data,
    required String mode,
    required String inputType,
    required String audioPath,
  }) async {
    final user = _auth.currentUser;
    if (user == null) return;

    final status = data['status'] as String? ?? 'unknown';
    final isSpoof = status == 'spoof_detected';

    final authenticity = data['authenticity'] is Map
        ? Map<String, dynamic>.from(data['authenticity'] as Map)
        : <String, dynamic>{};

    final delivery = data['delivery'] is Map
        ? Map<String, dynamic>.from(data['delivery'] as Map)
        : <String, dynamic>{};

    final assessment = delivery['assessment'] is Map
        ? Map<String, dynamic>.from(delivery['assessment'] as Map)
        : <String, dynamic>{};

    final features = delivery['features'] is Map
        ? Map<String, dynamic>.from(delivery['features'] as Map)
        : <String, dynamic>{};

    final transcriptAnalysis = data['transcript_analysis'] is Map
        ? Map<String, dynamic>.from(data['transcript_analysis'] as Map)
        : <String, dynamic>{};

    final fillerWords = transcriptAnalysis['filler_words'] is Map
        ? Map<String, dynamic>.from(transcriptAnalysis['filler_words'] as Map)
        : <String, dynamic>{};

    final grammar = transcriptAnalysis['grammar'] is Map
        ? Map<String, dynamic>.from(transcriptAnalysis['grammar'] as Map)
        : <String, dynamic>{};

    final pronunciation = transcriptAnalysis['pronunciation'] is Map
        ? Map<String, dynamic>.from(transcriptAnalysis['pronunciation'] as Map)
        : <String, dynamic>{};

    final transcriptFeedback = transcriptAnalysis['feedback'] is List
        ? List<String>.from(transcriptAnalysis['feedback'])
        : <String>[];

    final feedback = data['feedback'] is List
        ? List<String>.from(data['feedback'])
        : <String>[];

    final userRef = _db.collection('users').doc(user.uid);

    await userRef.set({
      'email': user.email,
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));

    await userRef.collection('analyses').add({
      'createdAt': FieldValue.serverTimestamp(),

      // session info
      'mode': mode,
      'inputType': inputType,
      'audioPath': audioPath,
      'status': status,

      // Pipeline A
      'authenticityLabel': isSpoof ? 'spoof' : 'bonafide',
      'authenticityConfidence': authenticity['confidence'] ?? 0.0,

      // Pipeline B
      'overallLevel': assessment['overall_level'] ?? 'N/A',
      'fluencyScore': assessment['fluency_score'],
      'prosodyScore': assessment['prosody_score'],
      'speechDuration': features['speech_duration_sec'],
      'speakingRate': features['syllable_rate_per_min'],
      'pauseCount': features['pause_count'],

      // Pipeline C
      'transcript': transcriptAnalysis['transcript'] ?? '',
      'fillerCount': fillerWords['total'] ?? 0,
      'fillerPer100Words': fillerWords['per_100_words'] ?? 0.0,
      'grammarIssueCount': grammar['issue_count'] ?? 0,
      'pronunciationLevel': pronunciation['clarity_level'] ?? 'N/A',
      'transcriptFeedback': transcriptFeedback,

      // feedback
      'feedbackSummary': feedback.isNotEmpty ? feedback.first : '',
      'feedback': feedback,
      'rawJson': jsonEncode(data),
    });
  }

  Stream<QuerySnapshot<Map<String, dynamic>>> getUserAnalyses() {
    final user = _auth.currentUser;
    if (user == null) {
      return const Stream.empty();
    }

    return _db
        .collection('users')
        .doc(user.uid)
        .collection('analyses')
        .orderBy('createdAt', descending: true)
        .snapshots();
  }
}