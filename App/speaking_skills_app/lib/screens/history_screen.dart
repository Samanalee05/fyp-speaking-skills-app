import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../services/firestore_service.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  Color _levelColor(String level) {
    switch (level) {
      case 'High':
        return Colors.green[600]!;
      case 'Medium':
        return Colors.orange[600]!;
      case 'Low':
        return Colors.red[500]!;
      default:
        return Colors.grey[600]!;
    }
  }

  String _formatDate(dynamic timestamp) {
    if (timestamp is! Timestamp) return 'Unknown date';

    final date = timestamp.toDate();
    return '${date.day}/${date.month}/${date.year} '
        '${date.hour.toString().padLeft(2, '0')}:'
        '${date.minute.toString().padLeft(2, '0')}';
  }

  String _modeLabel(String mode) {
    return mode == 'public_speaking' ? 'Public Speaking' : 'Academic';
  }

  @override
  Widget build(BuildContext context) {
    final service = FirestoreService();

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FF),
      appBar: AppBar(
        title: const Text(
          'History',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
        stream: service.getUserAnalyses(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return const Center(child: Text('Could not load history.'));
          }

          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          final docs = (snapshot.data?.docs ?? [])
              .where((doc) => doc.data()['authenticityLabel'] != 'spoof')
              .toList();

          if (docs.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.history, size: 56, color: Color(0xFF94A3B8)),
                    SizedBox(height: 14),
                    Text(
                      'No practice history yet',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    SizedBox(height: 6),
                    Text(
                      'Complete a valid speech analysis to track your progress.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: docs.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final data = docs[index].data();

              final createdAt = data['createdAt'];
              final mode = (data['mode'] ?? 'academic').toString();
              final level = (data['overallLevel'] ?? 'N/A').toString();
              final feedback =
                  (data['feedbackSummary'] ?? 'No feedback saved.').toString();

              final fillerCount = data['fillerCount'] ?? 0;
              final grammarIssueCount = data['grammarIssueCount'] ?? 0;
              final pronunciationLevel =
                  (data['pronunciationLevel'] ?? 'N/A').toString();

              final levelColor = _levelColor(level);
              final modeLabel = _modeLabel(mode);

              return Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: levelColor.withOpacity(0.12),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(
                              Icons.record_voice_over,
                              color: levelColor,
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              '$modeLabel Practice',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 17,
                              ),
                            ),
                          ),
                          Text(
                            _formatDate(createdAt),
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _Tag(label: modeLabel, color: Colors.blue),
                          _Tag(label: level, color: levelColor),
                          _Tag(label: 'Fillers: $fillerCount', color: Colors.indigo),
                          _Tag(label: 'Grammar: $grammarIssueCount', color: Colors.purple),
                          _Tag(label: 'Clarity: $pronunciationLevel', color: Colors.teal),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        feedback,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 13,
                          color: Color(0xFF334155),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String label;
  final Color color;

  const _Tag({
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}