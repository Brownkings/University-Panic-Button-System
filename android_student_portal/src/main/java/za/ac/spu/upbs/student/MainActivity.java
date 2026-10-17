package za.ac.spu.upbs.student;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity implements LocationListener {

    private static final int REQ_LOCATION_PERMS = 1001;
    private static final int REQ_FILE_CHOOSER = 1002;
    private static final String PREFS_NAME = "upbs_student_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "https://youthalliance.co.za";
    private static final String LOCAL_BASE_URL = "http://192.168.240.1:8000";
    private static final String KEY_CALIBRATED_LAT = "calibrated_lat";
    private static final String KEY_CALIBRATED_LNG = "calibrated_lng";
    private static final String KEY_CALIBRATED_LABEL = "calibrated_label";
    public static final double SPU_CENTRAL_LAT = -28.742050;
    public static final double SPU_CENTRAL_LNG = 24.765100;

    WebView webView;
    ProgressBar progressBar;
    TextView gpsBadgeView;
    ValueCallback<Uri[]> filePathCallback;

    private View[] tabIndicators = new View[5];
    private TextView[] tabLabels = new TextView[5];
    private TextView[] tabSubtitles = new TextView[5];

    private LocationManager locationManager;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    volatile double currentLat = SPU_CENTRAL_LAT;
    volatile double currentLng = SPU_CENTRAL_LNG;
    volatile float currentAcc = 4.0f;
    volatile String currentSource = "SPU CAMPUS";
    String baseUrl = DEFAULT_BASE_URL;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        Window window = getWindow();
        if (window != null) {
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(Color.parseColor("#070B12"));
            window.setNavigationBarColor(Color.parseColor("#0B111E"));
        }

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        baseUrl = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL);

        // Load saved campus calibration or default to Sol Plaatje Central Campus
        currentLat = Double.longBitsToDouble(prefs.getLong(KEY_CALIBRATED_LAT, Double.doubleToRawLongBits(SPU_CENTRAL_LAT)));
        currentLng = Double.longBitsToDouble(prefs.getLong(KEY_CALIBRATED_LNG, Double.doubleToRawLongBits(SPU_CENTRAL_LNG)));
        currentSource = prefs.getString(KEY_CALIBRATED_LABEL, "SPU CAMPUS");
        currentAcc = 4.0f;

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#070B12"));
        root.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        // 1. Impeccable Mobile Status Header (Compact 50dp)
        LinearLayout headerBar = new LinearLayout(this);
        headerBar.setOrientation(LinearLayout.HORIZONTAL);
        headerBar.setGravity(Gravity.CENTER_VERTICAL);
        headerBar.setBackgroundColor(Color.parseColor("#0B111E"));
        headerBar.setPadding(dp(12), dp(8), dp(12), dp(8));
        headerBar.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        // Crimson SOS Beacon Emblem
        TextView brandPill = new TextView(this);
        brandPill.setText("SOS");
        brandPill.setTextColor(Color.WHITE);
        brandPill.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10.5f);
        brandPill.setTypeface(Typeface.DEFAULT_BOLD);
        brandPill.setGravity(Gravity.CENTER);
        brandPill.setPadding(dp(8), dp(5), dp(8), dp(5));
        GradientDrawable brandBg = new GradientDrawable();
        brandBg.setColor(Color.parseColor("#DC2626"));
        brandBg.setStroke(dp(1), Color.parseColor("#F87171"));
        brandBg.setCornerRadius(dp(6));
        brandPill.setBackground(brandBg);
        headerBar.addView(brandPill);

        // Two-line Brand Stack (UPBS GUARDIAN / STUDENT SAFETY PORTAL)
        LinearLayout brandStack = new LinearLayout(this);
        brandStack.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams stackParams = new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                1.0f
        );
        stackParams.setMargins(dp(10), 0, dp(6), 0);
        brandStack.setLayoutParams(stackParams);

        TextView titleView = new TextView(this);
        titleView.setText("UPBS GUARDIAN");
        titleView.setTextColor(Color.parseColor("#F8FAFC"));
        titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        brandStack.addView(titleView);

        TextView subTitleView = new TextView(this);
        subTitleView.setText("STUDENT SAFETY MOBILE");
        subTitleView.setTextColor(Color.parseColor("#64748B"));
        subTitleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 9.0f);
        subTitleView.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        brandStack.addView(subTitleView);

        headerBar.addView(brandStack);

        // Live Monospace GPS Pill (Tap to sync/reload, Long-press for server config)
        gpsBadgeView = new TextView(this);
        gpsBadgeView.setText("● GPS LOCKING");
        gpsBadgeView.setTextColor(Color.parseColor("#34D399"));
        gpsBadgeView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10.0f);
        gpsBadgeView.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        gpsBadgeView.setPadding(dp(9), dp(5), dp(9), dp(5));
        GradientDrawable gpsBg = new GradientDrawable();
        gpsBg.setColor(Color.parseColor("#131C2E"));
        gpsBg.setStroke(dp(1), Color.parseColor("#1E293B"));
        gpsBg.setCornerRadius(dp(999));
        gpsBadgeView.setBackground(gpsBg);
        gpsBadgeView.setOnClickListener(new GpsRefreshClickListener());
        gpsBadgeView.setOnLongClickListener(new ServerLongClickListener());
        headerBar.addView(gpsBadgeView);

        root.addView(headerBar);

        // 1px Header Structural Border
        View topDivider = new View(this);
        topDivider.setBackgroundColor(Color.parseColor("#1E293B"));
        topDivider.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(1)
        ));
        root.addView(topDivider);

        // 2. Thin Loading Progress Bar
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(2)
        ));
        progressBar.setVisibility(View.GONE);
        root.addView(progressBar);

        // 3. Central WebView Viewport
        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#070B12"));
        LinearLayout.LayoutParams webParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1.0f
        );
        webView.setLayoutParams(webParams);
        configureWebView();
        root.addView(webView);

        // 4. 1px Bottom Structural Border
        View bottomDivider = new View(this);
        bottomDivider.setBackgroundColor(Color.parseColor("#1E293B"));
        bottomDivider.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(1)
        ));
        root.addView(bottomDivider);

        // 5. Impeccable Fixed Bottom Tab Bar (Student Portal Only)
        LinearLayout bottomNav = new LinearLayout(this);
        bottomNav.setOrientation(LinearLayout.HORIZONTAL);
        bottomNav.setGravity(Gravity.CENTER_VERTICAL);
        bottomNav.setBackgroundColor(Color.parseColor("#0B111E"));
        bottomNav.setPadding(dp(4), 0, dp(4), dp(4));
        bottomNav.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(58)
        ));

        bottomNav.addView(createBottomTab(0, "SOS", "PANIC", "/home/", true));
        bottomNav.addView(createBottomTab(1, "STATUS", "TRACKER", "/dashboard/", false));
        bottomNav.addView(createBottomTab(2, "REPORT", "INCIDENT", "/incidents/new/", false));
        bottomNav.addView(createBottomTab(3, "RATE", "FEEDBACK", "/feedback/", false));
        bottomNav.addView(createBottomTab(4, "EXIT", "LOGOUT", "/logout/", false));

        root.addView(bottomNav);

        setContentView(root);
        updateActiveBottomTab(0);

        checkAndRequestLocationPermissions();
        fetchNetworkLocationFallback();

        webView.loadUrl(baseUrl + "/home/");
    }

    private View createBottomTab(int index, String title, String subtitle, String path, boolean isEmergency) {
        LinearLayout tab = new LinearLayout(this);
        tab.setOrientation(LinearLayout.VERTICAL);
        tab.setGravity(Gravity.CENTER);
        tab.setPadding(dp(4), 0, dp(4), dp(2));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.MATCH_PARENT,
                1.0f
        );
        tab.setLayoutParams(lp);

        // Top 2dp active indicator bar
        View indicator = new View(this);
        LinearLayout.LayoutParams indParams = new LinearLayout.LayoutParams(
                dp(28),
                dp(2)
        );
        indParams.setMargins(0, 0, 0, dp(6));
        indicator.setLayoutParams(indParams);
        indicator.setBackgroundColor(isEmergency ? Color.parseColor("#EF4444") : Color.TRANSPARENT);
        tab.addView(indicator);
        tabIndicators[index] = indicator;

        TextView labelView = new TextView(this);
        labelView.setText(title);
        labelView.setGravity(Gravity.CENTER);
        labelView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.0f);
        labelView.setTypeface(Typeface.DEFAULT_BOLD);
        labelView.setTextColor(isEmergency ? Color.parseColor("#F87171") : Color.parseColor("#E2E8F0"));
        tab.addView(labelView);
        tabLabels[index] = labelView;

        TextView subView = new TextView(this);
        subView.setText(subtitle);
        subView.setGravity(Gravity.CENTER);
        subView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 8.5f);
        subView.setTypeface(Typeface.MONOSPACE, Typeface.NORMAL);
        subView.setTextColor(Color.parseColor("#64748B"));
        tab.addView(subView);
        tabSubtitles[index] = subView;

        tab.setOnClickListener(new NavPathClickListener(index, path));
        return tab;
    }

    void updateActiveBottomTab(int activeIdx) {
        for (int i = 0; i < 5; i++) {
            if (tabIndicators[i] == null || tabLabels[i] == null || tabSubtitles[i] == null) continue;
            if (i == activeIdx) {
                int accent = (i == 0) ? Color.parseColor("#EF4444") : Color.parseColor("#3B82F6");
                tabIndicators[i].setBackgroundColor(accent);
                tabLabels[i].setTextColor(i == 0 ? Color.parseColor("#F87171") : Color.parseColor("#F8FAFC"));
                tabSubtitles[i].setTextColor(i == 0 ? Color.parseColor("#FCA5A5") : Color.parseColor("#93C5FD"));
            } else {
                tabIndicators[i].setBackgroundColor(Color.TRANSPARENT);
                tabLabels[i].setTextColor(i == 0 ? Color.parseColor("#F87171") : Color.parseColor("#94A3B8"));
                tabSubtitles[i].setTextColor(Color.parseColor("#64748B"));
            }
        }
    }

    void syncTabFromUrl(String url) {
        if (url == null) return;
        if (url.contains("/dashboard")) {
            updateActiveBottomTab(1);
        } else if (url.contains("/incidents")) {
            updateActiveBottomTab(2);
        } else if (url.contains("/feedback")) {
            updateActiveBottomTab(3);
        } else if (url.contains("/login")) {
            updateActiveBottomTab(4);
        } else {
            updateActiveBottomTab(0);
        }
    }

    @SuppressWarnings("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setGeolocationEnabled(true);
        settings.setLoadsImagesAutomatically(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setSupportZoom(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        settings.setUserAgentString("Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 UPBSStudentPortal/2.0");

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            cookieManager.setAcceptThirdPartyCookies(webView, true);
        }

        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.setWebViewClient(new PortalWebViewClient());
        webView.setWebChromeClient(new PortalWebChromeClient());
    }

    void injectGeolocationBridge() {
        if (webView == null) return;
        final String js = "(function() {"
                + "  document.documentElement.classList.add('upbs-student-mobile');"
                + "  if (document.body) document.body.classList.add('upbs-student-mobile');"
                + "  if (!document.getElementById('upbs-impeccable-mobile-css')) {"
                + "    var st = document.createElement('style');"
                + "    st.id = 'upbs-impeccable-mobile-css';"
                + "    st.textContent = `"
                + "      .navbar, .footer { display: none !important; }"
                + "      body { background: #070b12 !important; }"
                + "      .main-content { padding: 0.7rem 0.75rem 1.25rem 0.75rem !important; max-width: 100% !important; margin: 0 !important; }"
                + "      .card { padding: 0.85rem 0.95rem !important; margin-bottom: 0.75rem !important; border-radius: 12px !important; background: #0d131f !important; border: 1px solid rgba(148,163,184,0.16) !important; }"
                + "      .grid-2 { grid-template-columns: 1fr !important; gap: 0.55rem !important; }"
                + "      .auth-shell { margin: 0.35rem auto !important; }"
                + "      .auth-card { padding: 1.2rem 1.1rem !important; }"
                + "      .auth-brand-header { padding-bottom: 0.9rem !important; margin-bottom: 1rem !important; }"
                + "      .auth-heading { font-size: 1.15rem !important; }"
                + "      #studentGpsMap .leaflet-tile-pane { filter: invert(100%) hue-rotate(185deg) brightness(92%) contrast(94%) saturate(85%); }"
                + "    `;"
                + "    document.head.appendChild(st);"
                + "  }"
                + "  document.querySelectorAll('.role-switcher-panel').forEach(function(el) { el.remove(); });"
                + "  var authH = document.querySelector('.auth-heading');"
                + "  if (authH) authH.textContent = 'Student Safety Portal Sign-In';"
                + "  document.querySelectorAll('.nav-link-security, .nav-link-analytics, a[href*=\"/security\"], a[href*=\"/analytics\"], a[href*=\"/admin\"]').forEach(function(el) {"
                + "    el.remove();"
                + "  });"
                + "  if (document.getElementById('cadRadarMap') || document.querySelector('.reports-grid') || document.querySelector('.user-table')) {"
                + "    window.location.replace('/home/');"
                + "  }"
                + "  if (!window.AndroidBridge) return;"
                + "  function makePos(lat, lng, acc) {"
                + "    return {"
                + "      coords: {"
                + "        latitude: lat,"
                + "        longitude: lng,"
                + "        accuracy: acc || 20,"
                + "        altitude: null,"
                + "        altitudeAccuracy: null,"
                + "        heading: null,"
                + "        speed: null"
                + "      },"
                + "      timestamp: Date.now()"
                + "    };"
                + "  }"
                + "  var origGeo = navigator.geolocation;"
                + "  var origGet = origGeo ? origGeo.getCurrentPosition.bind(origGeo) : null;"
                + "  var customGeo = {"
                + "    getCurrentPosition: function(success, error, options) {"
                + "      try {"
                + "        if (window.AndroidBridge && window.AndroidBridge.hasLocation()) {"
                + "          var lat = window.AndroidBridge.getLatitude();"
                + "          var lng = window.AndroidBridge.getLongitude();"
                + "          var acc = window.AndroidBridge.getAccuracy();"
                + "          if (!isNaN(lat) && !isNaN(lng)) {"
                + "            success(makePos(lat, lng, acc));"
                + "            return;"
                + "          }"
                + "        }"
                + "      } catch (e) {}"
                + "      if (origGet) {"
                + "        origGet(success, function(err) {"
                + "          if (window.AndroidBridge && window.AndroidBridge.hasLocation()) {"
                + "            success(makePos(window.AndroidBridge.getLatitude(), window.AndroidBridge.getLongitude(), window.AndroidBridge.getAccuracy()));"
                + "          } else if (error) { error(err); }"
                + "        }, options);"
                + "      }"
                + "    },"
                + "    watchPosition: function(success, error, options) {"
                + "      customGeo.getCurrentPosition(success, error, options);"
                + "      return setInterval(function() {"
                + "        if (window.AndroidBridge && window.AndroidBridge.hasLocation()) {"
                + "          success(makePos(window.AndroidBridge.getLatitude(), window.AndroidBridge.getLongitude(), window.AndroidBridge.getAccuracy()));"
                + "        }"
                + "      }, 4000);"
                + "    },"
                + "    clearWatch: function(id) { clearInterval(id); }"
                + "  };"
                + "  try {"
                + "    Object.defineProperty(navigator, 'geolocation', { value: customGeo, configurable: true });"
                + "  } catch (e) {"
                + "    navigator.geolocation.getCurrentPosition = customGeo.getCurrentPosition;"
                + "    navigator.geolocation.watchPosition = customGeo.watchPosition;"
                + "  }"
                + "  if (window.L) {"
                + "    if (locSel && !document.getElementById('studentGpsMap')) {"
                + "      var mDiv = document.createElement('div');"
                + "      mDiv.id = 'studentGpsMap';"
                + "      mDiv.style.cssText = 'height: 175px; width: 100%; margin-top: 0.7rem; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.22); background: #0b111d; overflow: hidden;';"
                + "      locSel.parentNode.appendChild(mDiv);"
                + "    }"
                + "    var sMapEl = document.getElementById('studentGpsMap');"
                + "    if (sMapEl && !window.__upbsStudentMapObj && window.AndroidBridge && window.AndroidBridge.hasLocation()) {"
                + "      var sLat = window.AndroidBridge.getLatitude();"
                + "      var sLng = window.AndroidBridge.getLongitude();"
                + "      if (!isNaN(sLat) && !isNaN(sLng)) {"
                + "        try {"
                + "          var sm = L.map('studentGpsMap', { center: [sLat, sLng], zoom: 16, attributionControl: false });"
                + "          var tl = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 });"
                + "          tl.on('tileerror', function(ev) {"
                + "            if (ev.tile && !ev.tile.dataset.fb) {"
                + "              ev.tile.dataset.fb = '1';"
                + "              ev.tile.src = 'https://a.basemaps.cartocdn.com/rastertiles/voyager/' + ev.coords.z + '/' + ev.coords.x + '/' + ev.coords.y + '.png';"
                + "            }"
                + "          });"
                + "          tl.addTo(sm);"
                + "          L.circle([sLat, sLng], { radius: 18, color: '#ef4444', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.14 }).addTo(sm);"
                + "          L.circleMarker([sLat, sLng], { radius: 7, color: '#ffffff', weight: 2.5, fillColor: '#ef4444', fillOpacity: 1.0 }).addTo(sm);"
                + "          window.__upbsStudentMapObj = sm;"
                + "          setTimeout(function() { sm.invalidateSize(); }, 200);"
                + "        } catch (err) {}"
                + "      }"
                + "    } else if (window.__upbsStudentMapObj) {"
                + "      window.__upbsStudentMapObj.invalidateSize();"
                + "    }"
                + "  }"
                + "})();";

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            webView.evaluateJavascript(js, null);
        } else {
            webView.loadUrl("javascript:" + js);
        }
    }

    private void checkAndRequestLocationPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            boolean fine = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            boolean coarse = checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            if (!fine && !coarse) {
                requestPermissions(new String[]{
                        Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION
                }, REQ_LOCATION_PERMS);
                return;
            }
        }
        startLocationTracking();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_LOCATION_PERMS) {
            startLocationTracking();
            fetchNetworkLocationFallback();
        }
    }

    @SuppressWarnings("MissingPermission")
    void startLocationTracking() {
        try {
            locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            if (locationManager == null) return;

            List<String> providers = locationManager.getAllProviders();
            if (providers != null) {
                for (String provider : providers) {
                    try {
                        Location last = locationManager.getLastKnownLocation(provider);
                        if (last != null) {
                            updateNativeCoordinates(last.getLatitude(), last.getLongitude(), last.getAccuracy(), "ANDROID_" + provider.toUpperCase(Locale.US));
                        }
                        locationManager.requestLocationUpdates(provider, 3000L, 1.0f, this);
                    } catch (Exception ignored) {
                    }
                }
            }
        } catch (Exception ignored) {
        }
    }

    void fetchNetworkLocationFallback() {
        new Thread(new NetworkGeoFetcher()).start();
    }

    void updateNativeCoordinates(double lat, double lng, float acc, String source) {
        this.currentLat = lat;
        this.currentLng = lng;
        this.currentAcc = acc > 0 ? acc : 25.0f;
        this.currentSource = source;
        mainHandler.post(new UiCoordinateUpdater(lat, lng));
    }

    @Override
    public void onLocationChanged(Location location) {
        if (location != null) {
            String provider = location.getProvider() != null ? location.getProvider().toUpperCase(Locale.US) : "GPS";
            updateNativeCoordinates(location.getLatitude(), location.getLongitude(), location.getAccuracy(), "ANDROID_" + provider);
        }
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
    }

    @Override
    public void onProviderEnabled(String provider) {
    }

    @Override
    public void onProviderDisabled(String provider) {
    }

    void showServerConfigDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("UPBS Server Endpoint");
        final String[] options = new String[] {
            "Cloud Production (https://youthalliance.co.za)",
            "Local Host Dev (http://192.168.240.1:8000)",
            "Custom URL..."
        };
        builder.setItems(options, new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                if (which == 0) {
                    setServerEndpoint(DEFAULT_BASE_URL);
                } else if (which == 1) {
                    setServerEndpoint(LOCAL_BASE_URL);
                } else {
                    showCustomUrlDialog();
                }
            }
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    void setServerEndpoint(String url) {
        if (url == null) return;
        String trimmed = url.trim();
        if (trimmed.endsWith("/")) trimmed = trimmed.substring(0, trimmed.length() - 1);
        if (!trimmed.isEmpty()) {
            baseUrl = trimmed;
            getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                    .edit()
                    .putString(KEY_BASE_URL, baseUrl)
                    .apply();
            if (webView != null) {
                webView.loadUrl(baseUrl + "/home/");
            }
            Toast.makeText(this, "Connected: " + baseUrl, Toast.LENGTH_SHORT).show();
        }
    }

    void showCustomUrlDialog() {
        AlertDialog.Builder b = new AlertDialog.Builder(this);
        b.setTitle("Enter Custom Server URL");
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(baseUrl);
        b.setView(input);
        b.setPositiveButton("Connect", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                setServerEndpoint(input.getText().toString());
            }
        });
        b.setNegativeButton("Cancel", null);
        b.show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_FILE_CHOOSER) {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null) {
                String dataString = data.getDataString();
                if (dataString != null) {
                    results = new Uri[]{Uri.parse(dataString)};
                }
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView != null && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(this);
            } catch (Exception ignored) {
            }
        }
        super.onDestroy();
    }

    private int dp(int value) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP,
                value,
                getResources().getDisplayMetrics()
        );
    }

    void showLocationCalibrationDialog() {
        final String[] options = {
                "Live Hardware GNSS (Auto-Detect)",
                "SPU Central Campus (-28.7421, 24.7651)",
                "SPU Main Library (-28.7416, 24.7647)",
                "Science Block B - Labs (-28.7415, 24.7660)",
                "Student Centre (-28.7426, 24.7636)",
                "North Student Residence (-28.7388, 24.7654)",
                "Campus South Gate (-28.7452, 24.7650)",
                "Enter Custom Coordinates..."
        };

        final double[][] coords = {
                {Double.NaN, Double.NaN},
                {-28.742050, 24.765100},
                {-28.741600, 24.764700},
                {-28.741500, 24.766000},
                {-28.742600, 24.763600},
                {-28.738800, 24.765400},
                {-28.745200, 24.765000},
        };

        final String[] labels = {
                "LIVE GPS",
                "SPU CAMPUS",
                "MAIN LIBRARY",
                "SCIENCE BLOCK",
                "STUDENT CTR",
                "NORTH RES",
                "SOUTH GATE"
        };

        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Calibrate SOS Telemetry");
        builder.setItems(options, new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                if (which == 0) {
                    Toast.makeText(MainActivity.this, "Connecting to Hardware GNSS...", Toast.LENGTH_SHORT).show();
                    startLocationTracking();
                    fetchNetworkLocationFallback();
                } else if (which == options.length - 1) {
                    showCustomCoordinatesDialog();
                } else {
                    double lat = coords[which][0];
                    double lng = coords[which][1];
                    String lbl = labels[which];
                    setCalibratedLocation(lat, lng, 4.0f, lbl);
                    Toast.makeText(MainActivity.this, "Calibrated: " + options[which], Toast.LENGTH_SHORT).show();
                }
            }
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    void setCalibratedLocation(double lat, double lng, float acc, String label) {
        this.currentLat = lat;
        this.currentLng = lng;
        this.currentAcc = acc;
        this.currentSource = label;

        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putLong(KEY_CALIBRATED_LAT, Double.doubleToRawLongBits(lat))
                .putLong(KEY_CALIBRATED_LNG, Double.doubleToRawLongBits(lng))
                .putString(KEY_CALIBRATED_LABEL, label)
                .apply();

        mainHandler.post(new Runnable() {
            @Override
            public void run() {
                if (gpsBadgeView != null) {
                    gpsBadgeView.setText(String.format(Locale.US, "● %.4f, %.4f", lat, lng));
                    gpsBadgeView.setTextColor(Color.parseColor("#34D399"));
                }
                injectGeolocationBridge();
            }
        });
    }

    void showCustomCoordinatesDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Enter Benchmark Coordinates");

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(20), dp(10), dp(20), dp(10));

        final EditText latInput = new EditText(this);
        latInput.setHint("Latitude (e.g. -28.742050)");
        latInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        latInput.setText(String.format(Locale.US, "%.6f", currentLat));
        layout.addView(latInput);

        final EditText lngInput = new EditText(this);
        lngInput.setHint("Longitude (e.g. 24.765100)");
        lngInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        lngInput.setText(String.format(Locale.US, "%.6f", currentLng));
        layout.addView(lngInput);

        builder.setView(layout);
        builder.setPositiveButton("Apply Calibration", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                try {
                    double lat = Double.parseDouble(latInput.getText().toString().trim());
                    double lng = Double.parseDouble(lngInput.getText().toString().trim());
                    setCalibratedLocation(lat, lng, 4.0f, "CUSTOM_BENCHMARK");
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Invalid coordinate format", Toast.LENGTH_SHORT).show();
                }
            }
        });
        builder.setNegativeButton("Cancel", null);
        builder.show();
    }

    private class GpsRefreshClickListener implements View.OnClickListener {
        @Override
        public void onClick(View v) {
            showLocationCalibrationDialog();
        }
    }

    private class ServerLongClickListener implements View.OnLongClickListener {
        @Override
        public boolean onLongClick(View v) {
            showServerConfigDialog();
            return true;
        }
    }

    private class NavPathClickListener implements View.OnClickListener {
        private final int tabIndex;
        private final String path;

        NavPathClickListener(int tabIndex, String path) {
            this.tabIndex = tabIndex;
            this.path = path;
        }

        @Override
        public void onClick(View v) {
            updateActiveBottomTab(tabIndex);
            if (webView != null) {
                webView.loadUrl(baseUrl + path);
            }
        }
    }

    private class ServerSaveListener implements DialogInterface.OnClickListener {
        private final EditText input;

        ServerSaveListener(EditText input) {
            this.input = input;
        }

        @Override
        public void onClick(DialogInterface dialog, int which) {
            String newUrl = input.getText().toString().trim();
            if (newUrl.endsWith("/")) {
                newUrl = newUrl.substring(0, newUrl.length() - 1);
            }
            if (!newUrl.isEmpty()) {
                baseUrl = newUrl;
                getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                        .edit()
                        .putString(KEY_BASE_URL, baseUrl)
                        .apply();
                webView.loadUrl(baseUrl + "/home/");
            }
        }
    }

    private class ServerResetListener implements DialogInterface.OnClickListener {
        @Override
        public void onClick(DialogInterface dialog, int which) {
            baseUrl = DEFAULT_BASE_URL;
            getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                    .edit()
                    .putString(KEY_BASE_URL, baseUrl)
                    .apply();
            webView.loadUrl(baseUrl + "/home/");
        }
    }

    private class UiCoordinateUpdater implements Runnable {
        private final double lat;
        private final double lng;

        UiCoordinateUpdater(double lat, double lng) {
            this.lat = lat;
            this.lng = lng;
        }

        @Override
        public void run() {
            if (gpsBadgeView != null) {
                gpsBadgeView.setText(String.format(Locale.US, "● %.4f, %.4f", lat, lng));
                gpsBadgeView.setTextColor(Color.parseColor("#34D399"));
            }
            injectGeolocationBridge();
        }
    }

    private class NetworkGeoFetcher implements Runnable {
        @Override
        public void run() {
            try {
                URL url = new URL(baseUrl + "/alerts/api/resolve-location/");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(4000);
                conn.setReadTimeout(4000);
                conn.setRequestProperty("Accept", "application/json");
                conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 13; Mobile) UPBSStudentPortal/2.0");
                if (conn.getResponseCode() == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line);
                    }
                    reader.close();
                    JSONObject json = new JSONObject(sb.toString());
                    if (json.optBoolean("success", false) && json.has("latitude") && json.has("longitude")) {
                        double lat = json.getDouble("latitude");
                        double lng = json.getDouble("longitude");
                        // Guard against ISP IP hops defaulting to Johannesburg; accept Kimberley coordinates
                        if (lat >= -29.2 && lat <= -28.2 && lng >= 24.2 && lng <= 25.2) {
                            if (!"ANDROID_GPS".equals(currentSource)) {
                                updateNativeCoordinates(lat, lng, 15.0f, "CAMPUS_NET");
                            }
                        }
                    }
                }
            } catch (Exception ignored) {
            }
        }
    }

    private class PortalWebViewClient extends WebViewClient {
        private boolean isRestrictedPath(String urlString) {
            if (urlString == null) return false;
            try {
                Uri uri = Uri.parse(urlString);
                String path = uri.getPath();
                if (path == null) return false;
                String lower = path.toLowerCase(Locale.US);
                return lower.startsWith("/security") ||
                       lower.startsWith("/analytics") ||
                       lower.startsWith("/admin-portal") ||
                       lower.startsWith("/admin") ||
                       lower.startsWith("/users") ||
                       lower.startsWith("/user_management");
            } catch (Exception e) {
                return false;
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            return handleUri(uri);
        }

        @Override
        @SuppressWarnings("deprecation")
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            return handleUri(Uri.parse(url));
        }

        private boolean handleUri(Uri uri) {
            if (uri == null) return false;
            String scheme = uri.getScheme();
            if ("tel".equalsIgnoreCase(scheme) || "mailto".equalsIgnoreCase(scheme)) {
                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                    startActivity(intent);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Emergency Line: " + uri.getSchemeSpecificPart(), Toast.LENGTH_LONG).show();
                }
                return true;
            }

            if (isRestrictedPath(uri.toString())) {
                Toast.makeText(MainActivity.this, "Access Denied: Mobile App is restricted to the Student Safety Portal.", Toast.LENGTH_SHORT).show();
                if (webView != null) {
                    webView.post(new Runnable() {
                        @Override
                        public void run() {
                            webView.loadUrl(baseUrl + "/home/");
                        }
                    });
                }
                return true;
            }
            return false;
        }

        @Override
        public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            super.onPageStarted(view, url, favicon);
            if (isRestrictedPath(url)) {
                view.stopLoading();
                view.post(new Runnable() {
                    @Override
                    public void run() {
                        view.loadUrl(baseUrl + "/home/");
                    }
                });
                return;
            }
            progressBar.setVisibility(View.VISIBLE);
            syncTabFromUrl(url);
            injectGeolocationBridge();
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            super.onPageFinished(view, url);
            progressBar.setVisibility(View.GONE);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                CookieManager.getInstance().flush();
            }
            syncTabFromUrl(url);
            injectGeolocationBridge();
        }

        @Override
        public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
            super.onReceivedError(view, errorCode, description, failingUrl);
            progressBar.setVisibility(View.GONE);
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
            handler.cancel();
            progressBar.setVisibility(View.GONE);
            Toast.makeText(MainActivity.this, "SSL Security Warning: Untrusted connection rejected.", Toast.LENGTH_LONG).show();
        }
    }

    private class PortalWebChromeClient extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView view, int newProgress) {
            progressBar.setProgress(newProgress);
            if (newProgress >= 100) {
                progressBar.setVisibility(View.GONE);
            } else {
                progressBar.setVisibility(View.VISIBLE);
            }
        }

        @Override
        public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
            callback.invoke(origin, true, false);
        }

        @Override
        public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback, FileChooserParams fileChooserParams) {
            if (MainActivity.this.filePathCallback != null) {
                MainActivity.this.filePathCallback.onReceiveValue(null);
            }
            MainActivity.this.filePathCallback = callback;
            try {
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                startActivityForResult(Intent.createChooser(intent, "Attach Incident Evidence"), REQ_FILE_CHOOSER);
            } catch (Exception e) {
                MainActivity.this.filePathCallback = null;
                return false;
            }
            return true;
        }
    }

    public class AndroidBridge {
        @JavascriptInterface
        public boolean hasLocation() {
            return !Double.isNaN(currentLat) && !Double.isNaN(currentLng);
        }

        @JavascriptInterface
        public double getLatitude() {
            return currentLat;
        }

        @JavascriptInterface
        public double getLongitude() {
            return currentLng;
        }

        @JavascriptInterface
        public float getAccuracy() {
            return currentAcc;
        }

        @JavascriptInterface
        public String getSource() {
            return currentSource;
        }

        @JavascriptInterface
        public void vibrate(long milliseconds) {
            try {
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v != null) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        v.vibrate(VibrationEffect.createOneShot(milliseconds, VibrationEffect.DEFAULT_AMPLITUDE));
                    } else {
                        v.vibrate(milliseconds);
                    }
                }
            } catch (Exception ignored) {
            }
        }
    }
}
