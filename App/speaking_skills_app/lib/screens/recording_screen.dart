import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import 'processing_screen.dart';

class RecordingScreen extends StatefulWidget {
  final String mode;
  final bool showBackButton;
  final ValueChanged<String>? onModeChanged;

  const RecordingScreen({
    super.key,
    required this.mode,
    this.showBackButton = true,
    this.onModeChanged,
  });

  @override
  State<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends State<RecordingScreen>
    with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();

  late String _selectedMode;
  _ReadAloudPassage _selectedPassage = _readAloudPassages.first;

  bool _isRecording = false;
  bool _hasRecording = false;
  String? _recordingPath;
  int _seconds = 0;

  Timer? _timer;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();

    _selectedMode = widget.mode;

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.15).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _pulseController.stop();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulseController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  String _formatTime(int seconds) {
    return '${(seconds ~/ 60).toString().padLeft(2, '0')}:'
        '${(seconds % 60).toString().padLeft(2, '0')}';
  }

  String _modeDescription(String mode) {
    switch (mode) {
      case 'academic':
        return 'Presentations, vivas, seminars';
      case 'public_speaking':
        return 'Speeches, talks, interviews';
      case 'read_aloud':
        return 'Read a passage for pronunciation and clarity practice';
      default:
        return '';
    }
  }

  void _changeMode(String mode) {
    if (_isRecording) return;

    setState(() {
      _selectedMode = mode;
      _hasRecording = false;
      _recordingPath = null;
      _seconds = 0;
    });

    widget.onModeChanged?.call(mode);
  }

  Future<void> _startRecording() async {
    final hasPermission = await _recorder.hasPermission();

    if (!hasPermission) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Microphone permission denied.')),
      );
      return;
    }

    final dir = await getTemporaryDirectory();
    final path =
        '${dir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.wav';

    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav),
      path: path,
    );

    if (!mounted) return;

    setState(() {
      _isRecording = true;
      _hasRecording = false;
      _recordingPath = null;
      _seconds = 0;
    });

    _pulseController.repeat(reverse: true);

    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _seconds++);
    });
  }

  Future<void> _stopRecording() async {
    _timer?.cancel();
    _pulseController.stop();

    final path = await _recorder.stop();

    if (!mounted) return;

    setState(() {
      _isRecording = false;
      _hasRecording = true;
      _recordingPath = path;
    });
  }

  void _submit() {
    if (_recordingPath == null) return;

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ProcessingScreen(
          audioPath: _recordingPath!,
          mode: _selectedMode,
          expectedText: _selectedMode == 'read_aloud' ? _selectedPassage.text : null,
        ),
      ),
    );
  }

  Future<void> _pickAudioFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.audio,
    );

    if (result == null || result.files.single.path == null) {
      return;
    }

    final path = result.files.single.path!;

    if (!mounted) return;

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ProcessingScreen(
          audioPath: path,
          mode: _selectedMode,
          expectedText: _selectedMode == 'read_aloud' ? _selectedPassage.text : null,
        ),
      ),
    );
  }

  Future<void> _showPassageSelector() async {
    if (_isRecording) return;

    final selected = await showModalBottomSheet<_ReadAloudPassage>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) {
        return _PassageSelectorSheet(
          selectedPassage: _selectedPassage,
          passages: _readAloudPassages,
        );
      },
    );

    if (selected == null) return;

    setState(() {
      _selectedPassage = selected;
      _hasRecording = false;
      _recordingPath = null;
      _seconds = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isReadAloud = _selectedMode == 'read_aloud';

    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FF),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: widget.showBackButton ? const BackButton() : null,
        automaticallyImplyLeading: widget.showBackButton,
        title: const Text(
          'Record Practice',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ModeSelector(
                selectedMode: _selectedMode,
                enabled: !_isRecording,
                onChanged: _changeMode,
              ),
              const SizedBox(height: 10),
              Text(
                _modeDescription(_selectedMode),
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF64748B),
                  fontSize: 13,
                ),
              ),

              if (isReadAloud) ...[
                const SizedBox(height: 18),
                _ReadAloudPassageCard(
                  passage: _selectedPassage,
                  onChange: _showPassageSelector,
                ),
              ],

              const SizedBox(height: 38),

              Text(
                _formatTime(_seconds),
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 64,
                  fontWeight: FontWeight.w200,
                  letterSpacing: 4,
                  color: Color(0xFF2E75B6),
                ),
              ),
              const SizedBox(height: 8),

              Text(
                _isRecording
                    ? 'Recording...'
                    : _hasRecording
                        ? 'Recording complete'
                        : 'Tap to start recording',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF64748B),
                  fontSize: 16,
                ),
              ),

              if (_seconds > 0 && _seconds < 30 && _isRecording) ...[
                const SizedBox(height: 8),
                Text(
                  isReadAloud
                      ? 'Keep reading the passage naturally'
                      : 'Keep going — aim for at least 30 seconds',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.orange[700],
                    fontSize: 13,
                  ),
                ),
              ],

              const SizedBox(height: 42),

              Center(
                child: ScaleTransition(
                  scale: _isRecording
                      ? _pulseAnimation
                      : const AlwaysStoppedAnimation(1.0),
                  child: GestureDetector(
                    onTap: _isRecording ? _stopRecording : _startRecording,
                    child: Container(
                      width: 116,
                      height: 116,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isRecording
                            ? Colors.red[600]
                            : const Color(0xFF2E75B6),
                        boxShadow: [
                          BoxShadow(
                            color: (_isRecording
                                    ? Colors.red[600]!
                                    : const Color(0xFF2E75B6))
                                .withOpacity(0.35),
                            blurRadius: 24,
                            spreadRadius: 6,
                          ),
                        ],
                      ),
                      child: Icon(
                        _isRecording ? Icons.stop : Icons.mic,
                        color: Colors.white,
                        size: 48,
                      ),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 12),

              Text(
                _isRecording ? 'Tap to stop' : '',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                ),
              ),

              const SizedBox(height: 48),

              OutlinedButton.icon(
                onPressed: _isRecording ? null : _pickAudioFile,
                icon: const Icon(Icons.upload_file),
                label: const Text('Upload Audio File'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
              ),

              if (_hasRecording) ...[
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _submit,
                  icon: const Icon(Icons.analytics_outlined),
                  label: const Text('Analyse Recording'),
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: _startRecording,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Record Again'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ModeSelector extends StatelessWidget {
  final String selectedMode;
  final bool enabled;
  final ValueChanged<String> onChanged;

  const _ModeSelector({
    required this.selectedMode,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 74,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          _ModeTab(
            label: 'Academic',
            icon: Icons.school_outlined,
            selected: selectedMode == 'academic',
            enabled: enabled,
            onTap: () => onChanged('academic'),
          ),
          _ModeTab(
            label: 'Public',
            icon: Icons.mic_outlined,
            selected: selectedMode == 'public_speaking',
            enabled: enabled,
            onTap: () => onChanged('public_speaking'),
          ),
          _ModeTab(
            label: 'Read Aloud',
            icon: Icons.menu_book_outlined,
            selected: selectedMode == 'read_aloud',
            enabled: enabled,
            onTap: () => onChanged('read_aloud'),
          ),
        ],
      ),
    );
  }
}

class _ModeTab extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  const _ModeTab({
    required this.label,
    required this.icon,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: enabled ? onTap : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
          decoration: BoxDecoration(
            color: selected ? const Color(0xFFE3F0FF) : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                selected ? Icons.check : icon,
                size: 22,
                color: const Color(0xFF0F172A),
              ),
              const SizedBox(height: 4),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ReadAloudPassageCard extends StatelessWidget {
  final _ReadAloudPassage passage;
  final VoidCallback onChange;

  const _ReadAloudPassageCard({
    required this.passage,
    required this.onChange,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: const Color(0xFFEFF6FF),
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.menu_book_outlined, color: Color(0xFF2E75B6)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    passage.title,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                      color: Color(0xFF0F172A),
                    ),
                  ),
                ),
                TextButton(
                  onPressed: onChange,
                  child: const Text('Change'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              passage.text,
              style: const TextStyle(
                fontSize: 13,
                height: 1.45,
                color: Color(0xFF334155),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PassageSelectorSheet extends StatelessWidget {
  final _ReadAloudPassage selectedPassage;
  final List<_ReadAloudPassage> passages;

  const _PassageSelectorSheet({
    required this.selectedPassage,
    required this.passages,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFFF8FAFC),
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Select Passage',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...passages.map(
              (passage) {
                final selected = passage.id == selectedPassage.id;

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => Navigator.pop(context, passage),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: selected
                              ? const Color(0xFF2E75B6)
                              : const Color(0xFFE2E8F0),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            passage.title,
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            passage.text,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 12,
                              height: 1.35,
                              color: Color(0xFF475569),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ReadAloudPassage {
  final String id;
  final String title;
  final String text;

  const _ReadAloudPassage({
    required this.id,
    required this.title,
    required this.text,
  });
}

const List<_ReadAloudPassage> _readAloudPassages = [
  _ReadAloudPassage(
    id: 'student_presentations',
    title: 'Student Presentations',
    text:
        'Every year, millions of students around the world prepare to give '
        'presentations in front of their classmates and teachers. For many, this '
        'can be a stressful experience. However, regular practice is one of the '
        'most effective ways to build confidence and improve communication skills.',
  ),
  _ReadAloudPassage(
    id: 'climate_change',
    title: 'Climate Change',
    text:
        'Climate change represents one of the most pressing challenges of our '
        'time. Rising global temperatures, melting ice caps, and extreme weather '
        'events are just some of the consequences we face. Scientists worldwide '
        'agree that immediate action is necessary to reduce future risks.',
  ),
  _ReadAloudPassage(
    id: 'technology_learning',
    title: 'Technology and Learning',
    text:
        'Technology has changed the way students learn and communicate. Online '
        'resources, mobile applications, and digital classrooms can make learning '
        'more flexible and accessible. However, students still need discipline '
        'and practice to develop strong communication skills.',
  ),
];