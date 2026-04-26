import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'screens/app_shell.dart';

void main() {
  runApp(const SpeakingSkillsApp());
}

class SpeakingSkillsApp extends StatelessWidget {
  const SpeakingSkillsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Speaking Skills',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E75B6),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      home: const AppShell(),
    );
  }
}