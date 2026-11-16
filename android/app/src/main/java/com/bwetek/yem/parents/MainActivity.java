package com.bwetek.yem.parents;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String HOST = "yem-api.onrender.com";
    private static final String HOME = "https://" + HOST + "/parents-app/#/parents";
    private WebView web;
    private LinearLayout error;
    private TextView errorText;
    private ProgressBar progress;
    private boolean mainFailed;

    static boolean trustedPage(Uri uri) {
        return uri != null && "https".equals(uri.getScheme())
                && HOST.equals(uri.getHost()) && uri.getUserInfo() == null
                && (uri.getPort() == -1 || uri.getPort() == 443)
                && "/parents-app/".equals(uri.getPath());
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.WHITE);
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        layout.addView(progress, new LinearLayout.LayoutParams(-1, 6));
        error = new LinearLayout(this);
        error.setOrientation(LinearLayout.VERTICAL);
        error.setPadding(24, 24, 24, 24);
        errorText = new TextView(this);
        error.addView(errorText);
        Button retry = new Button(this);
        retry.setText("Réessayer");
        retry.setOnClickListener(v -> openHome());
        error.addView(retry);
        error.setVisibility(View.GONE);
        layout.addView(error);
        web = new WebView(this);
        layout.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(layout);

        WebView.setWebContentsDebuggingEnabled(false);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);

        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value == 100 ? View.GONE : View.VISIBLE);
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return true;
                if (trustedPage(request.getUrl())) return false;
                Toast.makeText(MainActivity.this, "Lien indisponible dans cette version de test.", Toast.LENGTH_SHORT).show();
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (!trustedPage(Uri.parse(url))) {
                    view.stopLoading();
                    showError("Adresse non autorisée.");
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError problem) {
                if (request.isForMainFrame()) showError("Connexion indisponible. Vérifiez Internet puis réessayez.");
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame()) showError("L’espace YEM Parents est indisponible ou pas encore déployé.");
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError problem) {
                handler.cancel();
                showError("Connexion sécurisée impossible. Aucun certificat invalide ne sera accepté.");
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (!mainFailed && trustedPage(Uri.parse(url))) {
                    error.setVisibility(View.GONE);
                    web.setVisibility(View.VISIBLE);
                }
            }
        });
        web.setDownloadListener((url, agent, disposition, mime, size) ->
                Toast.makeText(this, "Téléchargements PDF : prochain lot Android.", Toast.LENGTH_LONG).show());
        openHome();
    }

    private void openHome() {
        mainFailed = false;
        error.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        web.loadUrl(HOME);
    }

    private void showError(String message) {
        mainFailed = true;
        web.setVisibility(View.INVISIBLE);
        errorText.setText(message);
        error.setVisibility(View.VISIBLE);
        progress.setVisibility(View.GONE);
    }

    @Override public void onBackPressed() {
        if (web.canGoBack() && !mainFailed) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (web != null) {
            web.stopLoading();
            web.destroy();
        }
        super.onDestroy();
    }
}
