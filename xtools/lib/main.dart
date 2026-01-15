import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/app_state.dart';
import 'screens/xcode_dashboard.dart';

void main() {
  runApp(const XToolsApp());
}

class XToolsApp extends StatelessWidget {
  const XToolsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AppState()),
      ],
      child: MaterialApp(
        title: 'XTools',
        theme: ThemeData(
          brightness: Brightness.dark,
          primarySwatch: Colors.blue,
          scaffoldBackgroundColor: Colors.grey[950],
          appBarTheme: AppBarTheme(
            backgroundColor: Colors.grey[900],
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: Colors.grey[900],
            elevation: 2,
          ),
        ),
        home: const XCodeDashboard(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
