import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'results_screen.dart';


const String _backendBaseUrl = 'http://10.34.155.206:8000';


class ProcessingScreen extends StatefulWidget {
  final String audioPath;
  final String mode;
  const ProcessingScreen({super.key, required this.audioPath, required this.mode});

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen> {
  String _statusMessage = 'Checking authenticity...';
  bool _failed = false;
  String _errorMessage = '';

  @override
  void initState() {
    super.initState();
    _runAnalysis();
  }

  String _guessInputType(String path) {
    final lower = path.toLowerCase();
    if (lower.contains('recording_')) {
      return 'recorded';
    }
    return 'uploaded';
  }

  String guessInputType(String path) {
    final lower = path.toLowerCase();
    if (lower.contains('recording_')) {
      return 'recorded';
    }
    return 'uploaded';
  }

  Future<void> _runAnalysis() async {
    try {
      setState(() => _statusMessage = 'Checking authenticity...');

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$_backendBaseUrl/analyze?mode=${widget.mode}'),
      );
      request.files.add(await http.MultipartFile.fromPath(
        'file',
        widget.audioPath,
        // ignore: deprecated_member_use
        contentType: null,
      ));

      setState(() => _statusMessage = 'Analysing delivery...');

      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 120),
      );
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        debugPrint('STATUS CODE: ${response.statusCode}'); //print for debugging
        debugPrint('RESPONSE BODY: ${response.body}'); //print fr debugging
        final data = jsonDecode(response.body);
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => ResultsScreen(
                data: data,
                audioPath: widget.audioPath,
                inputType: _guessInputType(widget.audioPath),
              ),
            ),
          );
        }
      } else {
        setState(() {
          _failed = true;
          _errorMessage = 'Server error: ${response.statusCode}\n${response.body}';
        });
      }
    } catch (e) {
      setState(() {
        _failed = true;
        _errorMessage = e.toString();
      });
    }
  }

  @override

  
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F8FF),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: _failed ? _buildError() : _buildLoading(),
          ),
        ),
      ),
    );
  }

  Widget _buildLoading() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const CircularProgressIndicator(
          color: Color(0xFF2E75B6),
          strokeWidth: 3,
        ),
        const SizedBox(height: 32),
        Text(
          _statusMessage,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 12),
        Text(
          'This may take up to 30 seconds',
          style: TextStyle(color: Colors.grey[500], fontSize: 14),
        ),
      ],
    );
  }

  Widget _buildError() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline, size: 64, color: Colors.red),
        const SizedBox(height: 16),
        const Text('Something went wrong',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(_errorMessage,
            style: TextStyle(color: Colors.grey[600], fontSize: 12),
            textAlign: TextAlign.center),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Go Back'),
        ),
      ],
    );
  }
}