import 'package:flutter/material.dart';

class ResultsScreen extends StatefulWidget {
  final Map<String, dynamic> data;
  final String? audioPath;
  final String inputType;

  const ResultsScreen({
    super.key,
    required this.data,
    this.audioPath,
    this.inputType = 'recorded',
  });

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  Map<String, dynamic> get data => widget.data;

  @override
  Widget build(BuildContext context) {
    final status = data['status'] as String? ?? 'unknown';
    final isSpoof = status == 'spoof_detected';

    final authenticity = data['authenticity'] is Map
        ? Map<String, dynamic>.from(data['authenticity'] as Map)
        : <String, dynamic>{};

    final feedback = data['feedback'] is List
        ? List<String>.from(data['feedback'])
        : <String>[];

    Map<String, dynamic>? assessment;
    Map<String, dynamic>? features;
    Map<String, dynamic>? transcriptAnalysis;

    final delivery = data['delivery'];
    if (!isSpoof && delivery is Map) {
      final deliveryMap = Map<String, dynamic>.from(delivery);

      if (deliveryMap['assessment'] is Map) {
        assessment = Map<String, dynamic>.from(deliveryMap['assessment']);
      }

      if (deliveryMap['features'] is Map) {
        features = Map<String, dynamic>.from(deliveryMap['features']);
      }
    }

    if (!isSpoof && data['transcript_analysis'] is Map) {
      transcriptAnalysis =
          Map<String, dynamic>.from(data['transcript_analysis'] as Map);
    }

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FF),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: const Text('Your Results',
            style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          TextButton(
            onPressed: () =>
                Navigator.popUntil(context, (route) => route.isFirst),
            child: const Text('Done'),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _AuthenticityBadge(
              isSpoof: isSpoof,
              confidence: ((authenticity['confidence'] ?? 0.0) as num).toDouble(),
            ),
            const SizedBox(height: 20),

            if (isSpoof) ...[
              _SpoofWarning(),
            ] else if (assessment != null) ...[
              _OverallLevelCard(assessment: assessment),
              const SizedBox(height: 20),
              _ScoreBreakdown(assessment: assessment),
              const SizedBox(height: 20),
              if (features != null) ...[
                _FeatureHighlights(features: features),
                const SizedBox(height: 20),
              ],
              if (transcriptAnalysis != null) ...[
                _TranscriptAnalysisCard(analysis: transcriptAnalysis),
                const SizedBox(height: 20),
              ],
              _FeedbackList(feedback: feedback),
              const SizedBox(height: 20),
            ],

            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () =>
                    Navigator.popUntil(context, (route) => route.isFirst),
                icon: const Icon(Icons.mic),
                label: const Text('Try Again'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

// ── Authenticity badge ────────────────────────────────────────────────────────

class _AuthenticityBadge extends StatelessWidget {
  final bool isSpoof;
  final double confidence;
  const _AuthenticityBadge({required this.isSpoof, required this.confidence});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: isSpoof ? Colors.red[50] : Colors.green[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isSpoof ? Colors.red[200]! : Colors.green[200]!,
        ),
      ),
      child: Row(
        children: [
          Icon(
            isSpoof ? Icons.warning_amber_rounded : Icons.verified_rounded,
            color: isSpoof ? Colors.red[700] : Colors.green[700],
            size: 24,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isSpoof ? 'Synthetic Audio Detected' : 'Verified Human Speech',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: isSpoof ? Colors.red[700] : Colors.green[700],
                  ),
                ),
                Text(
                  'Confidence: ${(confidence * 100).toStringAsFixed(1)}%',
                  style: TextStyle(
                    fontSize: 12,
                    color: isSpoof ? Colors.red[600] : Colors.green[600],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Spoof warning ─────────────────────────────────────────────────────────────

class _SpoofWarning extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.red[50],
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const Icon(Icons.block, size: 48, color: Colors.red),
            const SizedBox(height: 12),
            const Text(
              'Analysis Not Available',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
            const SizedBox(height: 8),
            Text(
              'This audio appears to be AI-generated or synthetic. '
              'Please re-record using your real voice for delivery feedback.\n\n'
              'If you believe this is an error, try recording in a quieter '
              'environment with your phone held closer to your mouth.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[700]),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Overall level card ────────────────────────────────────────────────────────

class _OverallLevelCard extends StatelessWidget {
  final Map<String, dynamic> assessment;
  const _OverallLevelCard({required this.assessment});

  Color _levelColor(String level) {
    switch (level) {
      case 'High':   return Colors.green[600]!;
      case 'Medium': return Colors.orange[600]!;
      default:       return Colors.red[600]!;
    }
  }

  String _levelDescription(String level) {
    switch (level) {
      case 'High':   return 'Strong delivery — well done!';
      case 'Medium': return 'Good delivery with room to grow';
      default:       return 'Keep practising — you\'ll improve';
    }
  }

  @override
  Widget build(BuildContext context) {
    final level = assessment['overall_level'] as String? ?? 'Medium';
    final mode  = assessment['mode'] as String? ?? 'academic';

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text('Overall Delivery Level',
                style: TextStyle(color: Colors.grey[600], fontSize: 14)),
            const SizedBox(height: 8),
            Text(
              level,
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: _levelColor(level),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              _levelDescription(level),
              style: TextStyle(color: Colors.grey[600], fontSize: 13),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.blue[50],
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                mode == 'academic' ? 'Academic Mode' : 'Public Speaking Mode',
                style: TextStyle(color: Colors.blue[700], fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Score breakdown ───────────────────────────────────────────────────────────

class _ScoreBreakdown extends StatelessWidget {
  final Map<String, dynamic> assessment;
  const _ScoreBreakdown({required this.assessment});

  String _scoreToLevel(double score) {
    if (score >= 2.67) return 'High';
    if (score >= 2.0)  return 'Medium';
    return 'Low';
  }

  Color _levelColor(String level) {
    switch (level) {
      case 'High':   return Colors.green[600]!;
      case 'Medium': return Colors.orange[600]!;
      default:       return Colors.red[500]!;
    }
  }

  @override
  Widget build(BuildContext context) {
    final fluency = (assessment['fluency_score'] as num).toDouble();
    final prosody = (assessment['prosody_score'] as num).toDouble();
    final fluencyLevel = _scoreToLevel(fluency);
    final prosodyLevel = _scoreToLevel(prosody);

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('Score Breakdown',
                    style:
                        TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(width: 6),
                Tooltip(
                  message:
                      'Fluency measures your pacing and pause usage.\n'
                      'Expressiveness measures pitch variation, loudness, and voice quality.',
                  child: Icon(Icons.info_outline,
                      size: 16, color: Colors.grey[500]),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _ScoreDimension(
              label: 'Fluency',
              sublabel: 'Pacing & pauses',
              level: fluencyLevel,
              score: fluency,
              color: _levelColor(fluencyLevel),
            ),
            const SizedBox(height: 12),
            _ScoreDimension(
              label: 'Expressiveness',
              sublabel: 'Pitch, loudness & voice quality',
              level: prosodyLevel,
              score: prosody,
              color: _levelColor(prosodyLevel),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScoreDimension extends StatelessWidget {
  final String label;
  final String sublabel;
  final String level;
  final double score;
  final Color color;

  const _ScoreDimension({
    required this.label,
    required this.sublabel,
    required this.level,
    required this.score,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(sublabel,
                    style:
                        TextStyle(fontSize: 11, color: Colors.grey[500])),
              ],
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(level,
                  style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.bold,
                      fontSize: 13)),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score / 3.0,
            backgroundColor: Colors.grey[200],
            valueColor: AlwaysStoppedAnimation<Color>(color),
            minHeight: 8,
          ),
        ),
      ],
    );
  }
}

// ── Feature highlights (expandable) ──────────────────────────────────────────

class _FeatureHighlights extends StatefulWidget {
  final Map<String, dynamic> features;
  const _FeatureHighlights({required this.features});

  @override
  State<_FeatureHighlights> createState() => _FeatureHighlightsState();
}

class _FeatureHighlightsState extends State<_FeatureHighlights> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final f = widget.features;
    final basicItems = [
      {
        'label': 'Speech Duration',
        'value': '${(f['speech_duration_sec'] as num).toStringAsFixed(1)}s',
        'icon': Icons.timer_outlined,
        'tip': 'Total time you were actively speaking (excluding pauses).',
      },
      {
        'label': 'Pause Count',
        'value': '${f['pause_count']}',
        'icon': Icons.pause_circle_outline,
        'tip': 'Number of pauses longer than 0.25 seconds detected.',
      },
      {
        'label': 'Speaking Rate',
        'value': '${(f['syllable_rate_per_min'] as num).toStringAsFixed(1)}/min',
        'icon': Icons.speed_outlined,
        'tip': 'Estimated syllables per minute. Typical presentations: 200–260/min.',
      },
      {
        'label': 'Voice Clarity',
        'value': '${(f['hnr'] as num).toStringAsFixed(1)} dB',
        'icon': Icons.graphic_eq_outlined,
        'tip': 'Harmonics-to-Noise Ratio. Higher = clearer, more projected voice. 20+ dB is strong.',
      },
    ];

    final advancedItems = [
      {
        'label': 'Avg Pause',
        'value': '${(f['avg_pause_duration_sec'] as num).toStringAsFixed(2)}s',
        'icon': Icons.hourglass_empty_outlined,
        'tip': 'Average length of each pause. Under 0.7s is natural.',
      },
      {
        'label': 'Hesitation',
        'value': '${((f['hesitation_ratio'] as num) * 100).toStringAsFixed(1)}%',
        'icon': Icons.timelapse_outlined,
        'tip': 'Percentage of total time spent in silence.',
      },
      {
        'label': 'Pitch Range',
        'value': '${(f['pitch_range_hz'] as num).toStringAsFixed(1)} Hz',
        'icon': Icons.multiline_chart_outlined,
        'tip': 'Range between your lowest and highest pitch. Wider = more expressive.',
      },
      {
        'label': 'Jitter',
        'value': '${((f['jitter'] as num) * 100).toStringAsFixed(2)}%',
        'icon': Icons.waves_outlined,
        'tip': 'Cycle-to-cycle pitch variation. Under 1% is normal. High = vocal tension.',
      },
    ];

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Feature Highlights',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 16),
            _featureGrid(basicItems),
            if (_expanded) ...[
              const SizedBox(height: 12),
              const Divider(),
              const SizedBox(height: 8),
              Text('Advanced Details',
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey[600])),
              const SizedBox(height: 10),
              _featureGrid(advancedItems),
            ],
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () => setState(() => _expanded = !_expanded),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    _expanded ? 'Show less' : 'Show more details',
                    style: const TextStyle(
                        color: Color(0xFF2E75B6),
                        fontWeight: FontWeight.w500,
                        fontSize: 13),
                  ),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    color: const Color(0xFF2E75B6),
                    size: 18,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _featureGrid(List<Map<String, Object>> items) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 2.2,
      children: items
          .map((item) => _FeatureChip(
                label: item['label'] as String,
                value: item['value'] as String,
                icon: item['icon'] as IconData,
                tip: item['tip'] as String,
              ))
          .toList(),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final String tip;

  const _FeatureChip({
    required this.label,
    required this.value,
    required this.icon,
    required this.tip,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tip,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.blue[50],
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Icon(icon, size: 14, color: Colors.blue[700]),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(label,
                      style: TextStyle(fontSize: 11, color: Colors.blue[700]),
                      overflow: TextOverflow.ellipsis),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(value,
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 14)),
          ],
        ),
      ),
    );
  }
}

// ── Transcript analysis ─────────────────────────────────────────────────────

class _TranscriptAnalysisCard extends StatefulWidget {
  final Map<String, dynamic> analysis;

  const _TranscriptAnalysisCard({required this.analysis});

  @override
  State<_TranscriptAnalysisCard> createState() => _TranscriptAnalysisCardState();
}

class _TranscriptAnalysisCardState extends State<_TranscriptAnalysisCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final transcript = (widget.analysis['transcript'] ?? '').toString();

    final filler = widget.analysis['filler_words'] is Map
        ? Map<String, dynamic>.from(widget.analysis['filler_words'] as Map)
        : <String, dynamic>{};

    final grammar = widget.analysis['grammar'] is Map
        ? Map<String, dynamic>.from(widget.analysis['grammar'] as Map)
        : <String, dynamic>{};

    final pronunciation = widget.analysis['pronunciation'] is Map
        ? Map<String, dynamic>.from(widget.analysis['pronunciation'] as Map)
        : <String, dynamic>{};

    final transcriptFeedback = widget.analysis['feedback'] is List
        ? List<String>.from(widget.analysis['feedback'])
        : <String>[];

    final fillerTotal = filler['total'] ?? 0;
    final grammarIssues = grammar['issue_count'] ?? 0;
    final clarityLevel = pronunciation['clarity_level'] ?? 'N/A';

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Transcript & Language Feedback',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 14),

            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _MiniTag(label: 'Fillers: $fillerTotal', color: Colors.blue),
                _MiniTag(
                  label: 'Grammar notes: $grammarIssues',
                  color: Colors.purple,
                ),
                _MiniTag(
                  label: 'Clarity: $clarityLevel',
                  color: Colors.teal,
                ),
              ],
            ),

            if (transcriptFeedback.isNotEmpty) ...[
              const SizedBox(height: 14),
              ...transcriptFeedback.take(3).map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.arrow_right,
                            size: 18,
                            color: Colors.grey,
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              item,
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
            ],

            if (transcript.isNotEmpty) ...[
              const Divider(height: 24),
              GestureDetector(
                onTap: () => setState(() => _expanded = !_expanded),
                child: Row(
                  children: [
                    const Icon(Icons.notes_outlined, size: 18),
                    const SizedBox(width: 8),
                    Text(
                      _expanded ? 'Hide transcript' : 'Show transcript',
                      style: const TextStyle(
                        color: Color(0xFF2E75B6),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Icon(
                      _expanded
                          ? Icons.keyboard_arrow_up
                          : Icons.keyboard_arrow_down,
                      color: const Color(0xFF2E75B6),
                    ),
                  ],
                ),
              ),
              if (_expanded) ...[
                const SizedBox(height: 12),
                Text(
                  transcript,
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.45,
                    color: Color(0xFF334155),
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _MiniTag extends StatelessWidget {
  final String label;
  final Color color;

  const _MiniTag({
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

// ── Feedback list ────────────────-────────────────────────────────────────

class _FeedbackList extends StatelessWidget {
  final List<String> feedback;
  const _FeedbackList({required this.feedback});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Feedback',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            ...feedback.asMap().entries.map((entry) {
              final i = entry.key;
              final text = entry.value;
              final isFirst = i == 0;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (isFirst)
                      const Icon(Icons.info_outline,
                          size: 18, color: Color(0xFF2E75B6))
                    else
                      const Icon(Icons.arrow_right,
                          size: 18, color: Colors.grey),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        text,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: isFirst
                              ? FontWeight.w600
                              : FontWeight.normal,
                          color: isFirst
                              ? const Color(0xFF2E75B6)
                              : Colors.grey[800],
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
