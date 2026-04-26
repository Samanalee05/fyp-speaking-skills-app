import 'dart:async';
import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:file_picker/file_picker.dart';
import 'processing_screen.dart';

class RecordingScreen extends StatefulWidget {
  final String mode;
  const RecordingScreen({super.key, required this.mode});

  @override
  State<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends State<RecordingScreen>
    with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
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
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
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

  Future<void> _startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Microphone permission denied.')),
        );
      }
      return;
    }

    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.wav';

    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav),
      path: path.replaceAll('.m4a', '.wav'),
    );

    setState(() {
      _isRecording = true;
      _hasRecording = false;
      _recordingPath = null;
      _seconds = 0;
    });

    _pulseController.repeat(reverse: true);
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _seconds++);
    });
  }

  Future<void> _stopRecording() async {
    _timer?.cancel();
    _pulseController.stop();
    final path = await _recorder.stop();
    setState(() {
      _isRecording = false;
      _hasRecording = true;
      _recordingPath = path;
    });
  }

  void _submit() {
    if (_recordingPath == null) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ProcessingScreen(
          audioPath: _recordingPath!,
          mode: widget.mode,
        ),
      ),
    );
  }

  //Upload Audio File
  Future<void> _pickAudioFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.audio,
    );

    if (result == null || result.files.single.path == null) {
      return;
    }

    final path = result.files.single.path!;

    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => ProcessingScreen(
          audioPath: path,
          mode: widget.mode,
        ),
      ),
    );
  }

  String _formatTime(int s) =>
      '${(s ~/ 60).toString().padLeft(2, '0')}:${(s % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FF),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: const BackButton(),
        title: Text(
          widget.mode == 'academic' ? 'Academic Mode' : 'Public Speaking Mode',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const SizedBox(height: 32),
              // Timer display
              Text(
                _formatTime(_seconds),
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
                style: TextStyle(color: Colors.grey[600], fontSize: 16),
              ),
              if (_seconds > 0 && _seconds < 30 && _isRecording) ...[
                const SizedBox(height: 8),
                Text(
                  'Keep going — aim for at least 30 seconds',
                  style: TextStyle(color: Colors.orange[700], fontSize: 13),
                ),
              ],
              const Spacer(),
              // Record button
              ScaleTransition(
                scale: _isRecording ? _pulseAnimation : const AlwaysStoppedAnimation(1.0),
                child: GestureDetector(
                  onTap: _isRecording ? _stopRecording : _startRecording,
                  child: Container(
                    width: 100,
                    height: 100,
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
                              .withOpacity(0.4),
                          blurRadius: 20,
                          spreadRadius: 4,
                        ),
                      ],
                    ),
                    child: Icon(
                      _isRecording ? Icons.stop : Icons.mic,
                      color: Colors.white,
                      size: 44,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _isRecording ? 'Tap to stop' : '',
                style: TextStyle(color: Colors.grey[500], fontSize: 13),
              ),
              const Spacer(),

              // Upload button
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _isRecording ? null : _pickAudioFile,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('Upload Audio File'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Submit button
              if (_hasRecording) ...[
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _submit,
                    icon: const Icon(Icons.analytics_outlined),
                    label: const Text('Analyse Recording'),
                    style: FilledButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _startRecording,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Record Again'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}