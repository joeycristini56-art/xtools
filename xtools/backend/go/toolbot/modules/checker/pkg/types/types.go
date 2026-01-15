package types

// CheckResult represents the result of an account check
type CheckResult int

const (
	SUCCESS CheckResult = iota
	FAILURE
	BAN
	CUSTOM
)

func (r CheckResult) String() string {
	switch r {
	case SUCCESS:
		return "Success"
	case FAILURE:
		return "Failure"
	case BAN:
		return "Ban"
	case CUSTOM:
		return "Custom"
	default:
		return "Unknown"
	}
}

// CapturedData holds captured account information
type CapturedData struct {
	DateRegistered string
	Balance        string
	CCInfo         string
	PaypalEmail    string
	Subscription1  string
	Subscription2  string
	Subscription3  string
	Country        string
}

// ProxyConfig represents proxy configuration
type ProxyConfig struct {
	HTTP  string
	HTTPS string
}

// ProxyWithLine represents a proxy with its line number
type ProxyWithLine struct {
	LineNum int
	Proxy   string
}

// AccountCombo represents an email:password combination with line number
type AccountCombo struct {
	Email    string
	Password string
	LineNum  int
}
