import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

class AppDatabase {
  AppDatabase._();

  static final AppDatabase instance = AppDatabase._();

  static Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;

    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'speaking_skills_app.db');

    _database = await openDatabase(
      path,
      version: 1,
      onCreate: _createDb,
    );

    return _database!;
  }

  Future<void> _createDb(Database db, int version) async {
    await db.execute('''
      CREATE TABLE analysis_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        input_type TEXT NOT NULL,
        audio_path TEXT,
        status TEXT NOT NULL,
        authenticity_label TEXT NOT NULL,
        authenticity_confidence REAL NOT NULL,
        overall_level TEXT NOT NULL,
        fluency_level TEXT NOT NULL,
        expressiveness_level TEXT NOT NULL,
        speech_duration REAL,
        speaking_rate REAL,
        pause_count INTEGER,
        feedback_summary TEXT NOT NULL,
        raw_json TEXT NOT NULL
      )
    ''');
  }
}