package database

import (
	"database/sql"
	"math/rand"

	_ "github.com/mattn/go-sqlite3"
)

type Database struct {
	EmailsDB    *sql.DB
	PasswordsDB *sql.DB
	CombosDB    *sql.DB
	UsersDB     *sql.DB
	DataDB      *sql.DB
	ProxiesDB   *sql.DB
}

type DatabaseConfig struct {
	EmailsPath    string
	PasswordsPath string
	CombosPath    string
	UsersPath     string
	DataPath      string
	ProxiesPath   string
}

func New(config DatabaseConfig) (*Database, error) {
	db := &Database{}

	// Open read-only databases with performance optimizations for large files
	// mode=ro ensures no accidental writes; cache=shared improves speed
	openReadOnly := func(path string) (*sql.DB, error) {
		return sql.Open("sqlite3", path+"?mode=ro&_query_only=true&_cache=shared")
	}

	var err error
	if db.EmailsDB, err = openReadOnly(config.EmailsPath); err != nil {
		return nil, err
	}
	if db.PasswordsDB, err = openReadOnly(config.PasswordsPath); err != nil {
		return nil, err
	}
	if db.CombosDB, err = openReadOnly(config.CombosPath); err != nil {
		return nil, err
	}
	
	// Standard databases (Users, Data, Proxies) remain as originally defined
	if db.UsersDB, err = sql.Open("sqlite3", config.UsersPath); err != nil {
		return nil, err
	}
	if db.DataDB, err = sql.Open("sqlite3", config.DataPath); err != nil {
		return nil, err
	}
	if db.ProxiesDB, err = sql.Open("sqlite3", config.ProxiesPath); err != nil {
		return nil, err
	}

	// Initialize tables if they don't exist
	if err := db.initUsersTable(); err != nil {
		return nil, err
	}
	if err := db.initDataTable(); err != nil {
		return nil, err
	}
	if err := db.initProxiesTable(); err != nil {
		return nil, err
	}

	return db, nil
}

func (db *Database) initUsersTable() error {
	query := `
	CREATE TABLE IF NOT EXISTS users (
		user_id INTEGER PRIMARY KEY,
		username TEXT,
		first_name TEXT,
		api_key TEXT DEFAULT '',
		daily_search_count INTEGER DEFAULT 0,
		daily_download_count INTEGER DEFAULT 0,
		total_search_count INTEGER DEFAULT 0,
		total_download_count INTEGER DEFAULT 0,
		daily_limit INTEGER DEFAULT 3,
		daily_download_limit INTEGER DEFAULT 10000,
		has_custom_search_limit INTEGER DEFAULT 0,
		has_custom_download_limit INTEGER DEFAULT 0,
		is_banned INTEGER DEFAULT 0,
		created_at DATETIME,
		last_activity DATETIME,
		last_reset_date TEXT
	)`
	_, err := db.UsersDB.Exec(query)
	return err
}

func (db *Database) initDataTable() error {
	query := `
	CREATE TABLE IF NOT EXISTS data (
		key TEXT PRIMARY KEY,
		value TEXT,
		user_id INTEGER
	)`
	_, err := db.DataDB.Exec(query)
	return err
}

func (db *Database) initProxiesTable() error {
	query := `
	CREATE TABLE IF NOT EXISTS proxies (
		proxy_url TEXT PRIMARY KEY,
		status TEXT DEFAULT 'pending',
		response_time INTEGER DEFAULT 0,
		last_checked DATETIME,
		created_at DATETIME
	)`
	_, err := db.ProxiesDB.Exec(query)
	return err
}

// Internal helper: Instant random lookup via Primary Key index
func (db *Database) fastRandomLookup(targetDB *sql.DB, limit int) ([]string, error) {
	var maxID int64
	// Instant lookup of the highest ID in the table
	err := targetDB.QueryRow("SELECT MAX(id) FROM data").Scan(&maxID)
	if err != nil || maxID == 0 {
		return nil, err
	}

	results := make([]string, 0, limit)
	query := `SELECT val FROM data WHERE id = ? LIMIT 1`

	for len(results) < limit {
		// Pick a random number between 1 and the total row count
		randomID := rand.Int63n(maxID) + 1
		var val string
		err := targetDB.QueryRow(query, randomID).Scan(&val)
		if err == nil {
			results = append(results, val)
		}
		// If an ID is missing, the loop just tries another random ID
	}
	return results, nil
}

func (db *Database) GetRandomPasswords(limit int) ([]string, error) {
	return db.fastRandomLookup(db.PasswordsDB, limit)
}

func (db *Database) GetRandomCombos(limit int) ([]string, error) {
	return db.fastRandomLookup(db.CombosDB, limit)
}

func (db *Database) SearchEmails(domain string, limit int) ([]string, error) {
	// Removed ORDER BY RANDOM(). It is impossible to use on 50GB+.
	// This will now use the index on 'val' to find matches instantly.
	query := `SELECT val FROM data WHERE val LIKE ? LIMIT ?`
	pattern := "%" + domain + "%"

	rows, err := db.EmailsDB.Query(query, pattern, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []string
	for rows.Next() {
		var email string
		if err := rows.Scan(&email); err != nil {
			continue
		}
		results = append(results, email)
	}
	return results, nil
}

func (db *Database) SearchCombos(domain string, limit int) ([]string, error) {
	query := `SELECT val FROM data WHERE val LIKE ? LIMIT ?`
	pattern := "%" + domain + "%"

	rows, err := db.CombosDB.Query(query, pattern, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []string
	for rows.Next() {
		var combo string
		if err := rows.Scan(&combo); err != nil {
			continue
		}
		results = append(results, combo)
	}
	return results, nil
}

func (db *Database) GetTotalEmails() (int64, error) {
	var count int64
	err := db.EmailsDB.QueryRow(`SELECT COUNT(*) FROM data`).Scan(&count)
	return count, err
}

func (db *Database) GetTotalCombos() (int64, error) {
	var count int64
	err := db.CombosDB.QueryRow(`SELECT COUNT(*) FROM data`).Scan(&count)
	return count, err
}

func (db *Database) GetTotalPasswords() (int64, error) {
	var count int64
	err := db.PasswordsDB.QueryRow(`SELECT COUNT(*) FROM data`).Scan(&count)
	return count, err
}

// CountEmailsWithLimit counts emails matching a domain pattern up to a limit
func (db *Database) CountEmailsWithLimit(domain string, limit int) (int, error) {
	query := `SELECT COUNT(*) FROM (SELECT 1 FROM data WHERE val LIKE ? LIMIT ?)`
	pattern := "%" + domain + "%"
	var count int
	err := db.EmailsDB.QueryRow(query, pattern, limit).Scan(&count)
	return count, err
}

// CountCombosWithLimit counts combos matching a domain pattern up to a limit
func (db *Database) CountCombosWithLimit(domain string, limit int) (int, error) {
	query := `SELECT COUNT(*) FROM (SELECT 1 FROM data WHERE val LIKE ? LIMIT ?)`
	pattern := "%" + domain + "%"
	var count int
	err := db.CombosDB.QueryRow(query, pattern, limit).Scan(&count)
	return count, err
}

// CountPasswordsWithLimit counts passwords up to a limit
func (db *Database) CountPasswordsWithLimit(limit int) (int, error) {
	query := `SELECT COUNT(*) FROM (SELECT 1 FROM data LIMIT ?)`
	var count int
	err := db.PasswordsDB.QueryRow(query, limit).Scan(&count)
	return count, err
}

func (db *Database) Close() error {
	db.EmailsDB.Close()
	db.PasswordsDB.Close()
	db.CombosDB.Close()
	db.UsersDB.Close()
	db.DataDB.Close()
	db.ProxiesDB.Close()
	return nil
}
