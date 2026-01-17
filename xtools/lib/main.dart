import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'core/app_state.dart';
import 'screens/xcode_dashboard.dart';
import 'screens/onboarding_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final onboardingComplete = prefs.getBool('onboarding_complete') ?? false;
  runApp(XToolsApp(showOnboarding: !onboardingComplete));
}

class XToolsApp extends StatelessWidget {
  final bool showOnboarding;
  
  const XToolsApp({super.key, required this.showOnboarding});

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
        home: showOnboarding ? const OnboardingScreen() : const XCodeDashboard(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
