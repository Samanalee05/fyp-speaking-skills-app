import 'app_database.dart';
import 'analysis_result.dart';

class AnalysisResultDao {
  static const String tableName = 'analysis_results';

  Future<int> insertResult(AnalysisResult result) async {
    final db = await AppDatabase.instance.database;
    return db.insert(tableName, result.toMap());
  }

  Future<List<AnalysisResult>> getAllResults() async {
    final db = await AppDatabase.instance.database;

    final rows = await db.query(
      tableName,
      orderBy: 'created_at DESC',
    );

    return rows.map((row) => AnalysisResult.fromMap(row)).toList();
  }

  Future<void> deleteResult(int id) async {
    final db = await AppDatabase.instance.database;
    await db.delete(
      tableName,
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Future<void> clearAll() async {
    final db = await AppDatabase.instance.database;
    await db.delete(tableName);
  }
}