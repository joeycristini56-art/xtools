class XorthonLDashboard {
    constructor() {
        this.init();
        this.isAdminDashboard = window.location.pathname.includes('/admin/dashboard');
        this.isHealthPage = window.location.pathname === '/health';
    }

    init() {
        this.setupEventListeners();
        this.startAutoRefresh();
        
        // Initialize admin dashboard if on admin page
        if (this.isAdminDashboard) {
            this.initAdminDashboard();
        }
    }

    setupEventListeners() {
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }
        
        // Add visibility change listener for better resource management
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopAutoRefresh();
            } else {
                this.startAutoRefresh();
            }
        });
    }
    
    initAdminDashboard() {
        // Admin dashboard specific initialization
        this.updateAdminStats();
    }

    async refreshData() {
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<div class="loading"></div>';
        }

        try {
            if (this.isHealthPage) {
                await this.refreshHealthData();
            } else if (this.isAdminDashboard) {
                await this.updateAdminStats();
            }
        } catch (error) {
            console.error('Failed to refresh data:', error);
        } finally {
            if (refreshBtn) {
                refreshBtn.innerHTML = '↻';
            }
        }
    }
    
    async updateAdminStats() {
        try {
            const response = await fetch('/xorn/admin/stats/dashboard');
            const data = await response.json();
            
            if (data.success) {
                this.updateAdminMetrics(data);
            }
        } catch (error) {
            console.error('Failed to update admin stats:', error);
        }
    }
    
    updateAdminMetrics(data) {
        // Update API key stats
        this.updateElement('total-keys', data.api_keys.total);
        this.updateElement('active-keys', data.api_keys.active);
        
        // Update usage stats
        this.updateElement('total-requests', data.usage.total_requests);
        this.updateElement('success-rate', data.usage.success_rate.toFixed(1) + '%');
        this.updateElement('unique-users', data.usage.unique_users);
        this.updateElement('avg-response-time', Math.round(data.usage.avg_response_time) + 'ms');
        
        // Update real-time stats
        this.updateElement('active-users-hour', data.user_activity.active_users_hour);
        this.updateElement('active-users-day', data.user_activity.active_users_day);
        this.updateElement('hourly-requests', data.real_time.hourly_requests);
        this.updateElement('hourly-success-rate', data.real_time.hourly_success_rate.toFixed(1) + '%');
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            // Add animation effect
            element.style.transition = 'all 0.3s ease';
            element.style.transform = 'scale(1.05)';
            element.textContent = value;
            
            setTimeout(() => {
                element.style.transform = 'scale(1)';
            }, 300);
        }
    }

    async refreshHealthData() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            this.updateHealthMetrics(data);
        } catch (error) {
            throw error;
        }
    }

    updateHealthMetrics(data) {
        const statusIndicator = document.querySelector('.status-indicator');
        if (statusIndicator && data.status) {
            const statusClass = data.status === 'healthy' ? 'healthy' : 'error';
            statusIndicator.className = 'status-indicator status-' + statusClass;
        }

        this.updateMetric('uptime', this.formatUptime(data.uptime));
        this.updateMetric('cpu-usage', (data.system_info?.cpu_percent?.toFixed(1) || 0) + '%');
        this.updateMetric('memory-usage', (data.system_info?.memory_usage_mb?.toFixed(1) || 0) + ' MB');
        
        if (data.system_info?.disk_usage) {
            const diskUsedGB = (data.system_info.disk_usage.used / (1024 * 1024 * 1024)).toFixed(1);
            const diskTotalGB = (data.system_info.disk_usage.total / (1024 * 1024 * 1024)).toFixed(1);
            this.updateMetric('disk-usage', diskUsedGB + ' GB / ' + diskTotalGB + ' GB');
        }

        if (data.task_stats) {
            this.updateMetric('active-tasks', data.task_stats.active || 0);
            this.updateMetric('completed-tasks', data.task_stats.completed || 0);
            this.updateMetric('failed-tasks', data.task_stats.failed || 0);
        }

        if (data.solver_stats) {
            this.updateMetric('available-solvers', data.solver_stats.available || 0);
            this.updateMetric('total-solvers', data.solver_stats.total || 0);
        }
    }

    updateMetric(id, value) {
        const element = document.querySelector('[data-metric="' + id + '"]');
        if (element) {
            element.textContent = value;
        }
    }

    formatUptime(seconds) {
        
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) {
            return days + 'd ' + hours + 'h ' + minutes + 'm';
        } else if (hours > 0) {
            return hours + 'h ' + minutes + 'm';
        } else {
            return minutes + 'm';
        }
    }

    startAutoRefresh() {
        // Clear any existing interval
        this.stopAutoRefresh();
        
        // Start new interval
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, 30000);
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new XorthonLDashboard();
});
