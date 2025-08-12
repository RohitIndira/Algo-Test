// Dashboard JavaScript with Quantity Support

document.addEventListener('DOMContentLoaded', function() {
    // Initialize variables
    let isRunning = false;
    
    // Function to format timestamp consistently (India timezone)
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        // Format to India timezone consistently
        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Asia/Kolkata',
            hour12: true
        };
        return date.toLocaleString('en-IN', options);
    }
    
    // Update market time
    function updateMarketTime() {
        const now = new Date();
        document.getElementById('marketTime').textContent = now.toLocaleTimeString();
        document.getElementById('lastUpdated').textContent = now.toLocaleTimeString();
    }
    
    // Initial market time update
    updateMarketTime();
    
    // Update market time every second
    setInterval(updateMarketTime, 1000);
    
    // Load configuration
    function loadConfig() {
        fetch('/api/config')
            .then(response => response.json())
            .then(data => {
                document.getElementById('userIdValue').textContent = data.user_id || '-';
                document.getElementById('clientIdValue').textContent = data.client_id || '-';
                document.getElementById('orderQuantityValue').textContent = data.order_quantity || '-';
                document.getElementById('stopLossValue').textContent = `${(data.stop_loss_percentage * 100).toFixed(0)}% of High`;
                document.getElementById('buyPriceValue').textContent = `${data.buy_price_multiplier}x CMP`;
                document.getElementById('sellPriceValue').textContent = `${data.sell_price_multiplier}x CMP`;
                document.getElementById('maxPercentValue').textContent = `${data.max_percent_change}%`;
                document.getElementById('squareOffValue').textContent = data.auto_square_off_time || '-';
            })
            .catch(error => console.error('Error loading configuration:', error));
    }
    
    // Load signals with quantity
    function loadSignals() {
        fetch('/api/signals')
            .then(response => response.json())
            .then(data => {
                const signals = data.signals || [];
                const ordersTableBody = document.getElementById('ordersTableBody');
                const noOrdersMessage = document.getElementById('noOrdersMessage');
                const ordersTableContainer = document.getElementById('ordersTableContainer');
                
                // Clear existing rows
                ordersTableBody.innerHTML = '';
                
                if (signals.length > 0) {
                    // Hide no orders message and show table
                    noOrdersMessage.style.display = 'none';
                    ordersTableContainer.style.display = 'block';
                    
                    // Add signals to table with quantity
                    signals.forEach(signal => {
                        const row = document.createElement('tr');
                        
                        // Format timestamp consistently
                        const formattedTime = formatTimestamp(signal.timestamp);
                        
                        row.innerHTML = `
                            <td>${formattedTime}</td>
                            <td>${signal.symbol}</td>
                            <td><span class="badge ${signal.signal_type === 'BUY' ? 'bg-success' : 'bg-danger'}">${signal.signal_type}</span></td>
                            <td><strong>${signal.quantity}</strong></td>
                            <td>₹${signal.price.toFixed(2)}</td>
                            <td>₹${signal.total_value.toFixed(2)}</td>
                            <td><span class="badge bg-info">Simulated</span></td>
                        `;
                        
                        ordersTableBody.appendChild(row);
                    });
                    
                    // Update logs
                    updateLogs(signals);
                } else {
                    // Show no orders message and hide table
                    noOrdersMessage.style.display = 'block';
                    ordersTableContainer.style.display = 'none';
                }
            })
            .catch(error => console.error('Error loading signals:', error));
    }
    
    // Load positions with real-time data and quantity
    function loadPositions() {
        // First get positions from database
        fetch('/api/positions')
            .then(response => response.json())
            .then(data => {
                const positions = data.positions || [];
                const positionsTableBody = document.getElementById('positionsTableBody');
                const noPositionsMessage = document.getElementById('noPositionsMessage');
                const positionsTableContainer = document.getElementById('positionsTableContainer');
                
                // Clear existing rows
                positionsTableBody.innerHTML = '';
                
                if (positions.length > 0) {
                    // Hide no positions message and show table
                    noPositionsMessage.style.display = 'none';
                    positionsTableContainer.style.display = 'block';
                    
                    // Get real-time position data with PnL
                    fetch('/api/positions_realtime')
                        .then(response => response.json())
                        .then(realtimeData => {
                            const realtimePositions = realtimeData.positions || [];
                            
                            // Add positions to table with real-time data and quantity
                            positions.forEach(position => {
                                const row = document.createElement('tr');
                                
                                // Find matching real-time data
                                const realtimePos = realtimePositions.find(p => p.token === position.token);
                                const currentPrice = realtimePos ? realtimePos.current_price : position.entry_price;
                                const percentChange = realtimePos ? realtimePos.percent_gain : 0;
                                const totalCurrentValue = realtimePos ? realtimePos.total_current_value : position.total_entry_value;
                                
                                // Get 5-day high from tokens table
                                const fiveDayHigh = position.five_day_high || position.entry_price;
                                
                                // FIXED: Calculate P&L for display (current total value - total entry value)
                                const currentPnL = totalCurrentValue - position.total_entry_value;
                                const pnlClass = currentPnL > 0 ? 'positive-value' : (currentPnL < 0 ? 'negative-value' : 'neutral-value');
                                
                                // Format percentage change with color
                                const percentClass = percentChange > 0 ? 'positive-value' : (percentChange < 0 ? 'negative-value' : 'neutral-value');
                                
                                row.innerHTML = `
                                    <td>${position.symbol}</td>
                                    <td><strong>${position.quantity}</strong></td>
                                    <td>₹${currentPrice.toFixed(2)}</td>
                                    <td>₹${position.entry_price.toFixed(2)}</td>
                                    <td>₹${fiveDayHigh.toFixed(2)}</td>
                                    <td>₹${realtimePos ? realtimePos.day_high.toFixed(2) : currentPrice.toFixed(2)}</td>
                                    <td>₹${position.stop_loss.toFixed(2)}</td>
                                    <td class="${percentClass}">${percentChange.toFixed(2)}%</td>
                                    <td class="${pnlClass}">₹${totalCurrentValue.toFixed(2)} (P&L: ₹${currentPnL.toFixed(2)})</td>
                                    <td><span class="badge bg-success">Open</span></td>
                                `;
                                
                                positionsTableBody.appendChild(row);
                            });
                        })
                        .catch(error => {
                            // Fallback to basic display if real-time data fails
                            positions.forEach(position => {
                                const row = document.createElement('tr');
                                
                                row.innerHTML = `
                                    <td>${position.symbol}</td>
                                    <td><strong>${position.quantity}</strong></td>
                                    <td>₹${position.entry_price.toFixed(2)}</td>
                                    <td>₹${position.entry_price.toFixed(2)}</td>
                                    <td>₹${position.five_day_high.toFixed(2)}</td>
                                    <td>₹${position.entry_price.toFixed(2)}</td>
                                    <td>₹${position.stop_loss.toFixed(2)}</td>
                                    <td>0.00%</td>
                                    <td>₹${position.total_entry_value.toFixed(2)}</td>
                                    <td><span class="badge bg-success">Open</span></td>
                                `;
                                
                                positionsTableBody.appendChild(row);
                            });
                        });
                } else {
                    // Show no positions message and hide table
                    noPositionsMessage.style.display = 'block';
                    positionsTableContainer.style.display = 'none';
                }
                
                // Update position count
                document.getElementById('totalPositions').textContent = positions.length;
            })
            .catch(error => console.error('Error loading positions:', error));
    }
    
    // Load trade history with quantity
    function loadTradeHistory() {
        fetch('/api/trade_history')
            .then(response => response.json())
            .then(data => {
                const trades = data.trades || [];
                const tradesTableBody = document.getElementById('tradesTableBody');
                const noTradesMessage = document.getElementById('noTradesMessage');
                const tradesTableContainer = document.getElementById('tradesTableContainer');
                
                // Clear existing rows
                tradesTableBody.innerHTML = '';
                
                if (trades.length > 0) {
                    // Hide no trades message and show table
                    noTradesMessage.style.display = 'none';
                    tradesTableContainer.style.display = 'block';
                    
                    // Add trades to table with quantity
                    trades.forEach(trade => {
                        const row = document.createElement('tr');
                        
                        // Format timestamps consistently
                        const formattedEntryTime = formatTimestamp(trade.entry_time);
                        const formattedExitTime = formatTimestamp(trade.exit_time);
                        
                        // Calculate PnL class
                        const pnlClass = trade.pnl > 0 ? 'positive-value' : (trade.pnl < 0 ? 'negative-value' : 'neutral-value');
                        
                        row.innerHTML = `
                            <td>${trade.symbol}</td>
                            <td>₹${trade.entry_price.toFixed(2)}</td>
                            <td>₹${trade.exit_price.toFixed(2)}</td>
                            <td><strong>${trade.quantity}</strong></td>
                            <td>₹${trade.total_entry_value.toFixed(2)}</td>
                            <td>₹${trade.total_exit_value.toFixed(2)}</td>
                            <td>${formattedEntryTime}</td>
                            <td>${formattedExitTime}</td>
                            <td class="${pnlClass}">₹${trade.pnl.toFixed(2)}</td>
                            <td class="${pnlClass}">${trade.percent_gain.toFixed(2)}%</td>
                        `;
                        
                        tradesTableBody.appendChild(row);
                    });
                    
                    // REMOVED: Don't calculate realized PnL here - use API data instead
                    // The main dashboard cards get updated by updateStatistics() function
                } else {
                    // Show no trades message and hide table
                    noTradesMessage.style.display = 'block';
                    tradesTableContainer.style.display = 'none';
                }
            })
            .catch(error => console.error('Error loading trade history:', error));
    }
    
    // Load performance statistics
    function loadPerformanceStats() {
        fetch('/api/performance')
            .then(response => response.json())
            .then(data => {
                const stats = data.stats || {};
                
                // Update statistics
                document.getElementById('totalTradesStats').textContent = stats.total_trades || 0;
                document.getElementById('winningTradesStats').textContent = stats.winning_trades || 0;
                document.getElementById('losingTradesStats').textContent = stats.losing_trades || 0;
                document.getElementById('winRateStats').textContent = `${(stats.win_rate || 0).toFixed(2)}%`;
                
                document.getElementById('totalPnlStats').textContent = `₹${(stats.total_pnl || 0).toFixed(2)}`;
                document.getElementById('avgPnlStats').textContent = `₹${(stats.avg_pnl || 0).toFixed(2)}`;
                document.getElementById('maxProfitStats').textContent = `₹${(stats.max_profit || 0).toFixed(2)}`;
                document.getElementById('maxLossStats').textContent = `₹${(stats.max_loss || 0).toFixed(2)}`;
                
                // Set classes based on values
                document.getElementById('totalPnlStats').className = stats.total_pnl > 0 ? 'positive-value' : (stats.total_pnl < 0 ? 'negative-value' : 'neutral-value');
                document.getElementById('avgPnlStats').className = stats.avg_pnl > 0 ? 'positive-value' : (stats.avg_pnl < 0 ? 'negative-value' : 'neutral-value');
            })
            .catch(error => console.error('Error loading performance statistics:', error));
    }
    
    // Update logs with quantity information
    function updateLogs(signals) {
        const logsContainer = document.getElementById('logsContainer');
        
        // Clear existing logs
        logsContainer.innerHTML = '';
        
        // Add signals to logs with quantity
        signals.forEach(signal => {
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${signal.signal_type === 'BUY' ? 'log-entry-buy' : 'log-entry-sell'}`;
            
            // Format timestamp consistently
            const formattedTime = formatTimestamp(signal.timestamp);
            
            if (signal.signal_type === 'BUY') {
                logEntry.innerHTML = `[${formattedTime}] BUY SIGNAL: ${signal.symbol} - ${signal.quantity} shares at ₹${signal.price.toFixed(2)} each (Total: ₹${signal.total_value.toFixed(2)}), Stop Loss: ₹${signal.stop_loss.toFixed(2)}`;
            } else {
                logEntry.innerHTML = `[${formattedTime}] SELL SIGNAL: ${signal.symbol} - ${signal.quantity} shares at ₹${signal.price.toFixed(2)} each (Total: ₹${signal.total_value.toFixed(2)}), Stop Loss hit`;
            }
            
            logsContainer.appendChild(logEntry);
        });
    }
    
    // Check strategy status (for initial load and manual refresh only)
    function checkStrategyStatus() {
        fetch('/api/strategy/status')
            .then(response => response.json())
            .then(data => {
                const serverRunning = data.running;
                
                // Update running status and buttons
                isRunning = serverRunning;
                updateButtonStates();
                
                // Update status badge
                const statusBadge = document.getElementById('strategyStatus');
                if (isRunning) {
                    statusBadge.className = 'status-badge status-running';
                    statusBadge.innerHTML = '<i class="bi bi-circle-fill"></i> Running';
                } else {
                    statusBadge.className = 'status-badge status-stopped';
                    statusBadge.innerHTML = '<i class="bi bi-circle-fill"></i> Stopped';
                }
                
                // Update statistics
                updateStatistics(data);
            })
            .catch(error => console.error('Error checking strategy status:', error));
    }
    
    // Update statistics only (for auto-refresh without affecting buttons)
    function updateStatistics(data = null) {
        if (data) {
            // Use provided data
            document.getElementById('totalPositions').textContent = data.positions || 0;
            document.getElementById('totalOrders').textContent = data.orders || 0;
            document.getElementById('realizedPnl').textContent = `₹${(data.realized_pnl || 0).toFixed(2)}`;
            document.getElementById('unrealizedPnl').textContent = `₹${(data.unrealized_pnl || 0).toFixed(2)}`;
            
            // Set classes based on values
            document.getElementById('realizedPnl').className = `stats-value ${data.realized_pnl > 0 ? 'positive-value' : (data.realized_pnl < 0 ? 'negative-value' : 'neutral-value')}`;
            document.getElementById('unrealizedPnl').className = `stats-value ${data.unrealized_pnl > 0 ? 'positive-value' : (data.unrealized_pnl < 0 ? 'negative-value' : 'neutral-value')}`;
        } else {
            // Fetch fresh statistics data
            fetch('/api/strategy/status')
                .then(response => response.json())
                .then(data => {
                    // Only update statistics, don't touch button states
                    document.getElementById('totalPositions').textContent = data.positions || 0;
                    document.getElementById('totalOrders').textContent = data.orders || 0;
                    document.getElementById('realizedPnl').textContent = `₹${(data.realized_pnl || 0).toFixed(2)}`;
                    document.getElementById('unrealizedPnl').textContent = `₹${(data.unrealized_pnl || 0).toFixed(2)}`;
                    
                    // Set classes based on values
                    document.getElementById('realizedPnl').className = `stats-value ${data.realized_pnl > 0 ? 'positive-value' : (data.realized_pnl < 0 ? 'negative-value' : 'neutral-value')}`;
                    document.getElementById('unrealizedPnl').className = `stats-value ${data.unrealized_pnl > 0 ? 'positive-value' : (data.unrealized_pnl < 0 ? 'negative-value' : 'neutral-value')}`;
                })
                .catch(error => console.error('Error updating statistics:', error));
        }
    }
    
    // Function to update button states based on current status
    function updateButtonStates() {
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        
        if (isRunning) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }
    
    // Load all data
    function loadAllData() {
        loadConfig();
        loadSignals();
        loadPositions();
        loadTradeHistory();
        loadPerformanceStats();
        checkStrategyStatus();
        updateMarketTime();
    }
    
    // Initial data load
    loadAllData();
    
    // Refresh data every 5 seconds for faster real-time updates (but skip button updates)
    setInterval(function() {
        loadConfig();
        loadSignals();
        loadPositions();
        loadTradeHistory();
        loadPerformanceStats();
        updateStatistics(); // Update statistics without affecting buttons
        updateMarketTime();
    }, 5000);
    
    // Refresh button click handler
    document.getElementById('refreshBtn').addEventListener('click', function() {
        loadAllData();
    });
    
    // Start button click handler
    document.getElementById('startBtn').addEventListener('click', function() {
        // Immediately disable button to prevent double clicks
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Starting...';
        
        fetch('/api/strategy/start', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Update status
                isRunning = true;
                
                // Update UI
                const statusBadge = document.getElementById('strategyStatus');
                statusBadge.className = 'status-badge status-running';
                statusBadge.innerHTML = '<i class="bi bi-circle-fill"></i> Running';
                
                // Update buttons
                startBtn.innerHTML = '<i class="bi bi-play-fill"></i> Start Strategy';
                startBtn.disabled = true;
                stopBtn.disabled = false;
                
                // Show alert
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
                alertDiv.innerHTML = `
                    <i class="bi bi-check-circle-fill"></i> 
                    Strategy started successfully
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Insert alert before the form
                const card = document.querySelector('.card');
                card.parentNode.insertBefore(alertDiv, card.nextSibling);
                
                // Auto dismiss after 5 seconds
                setTimeout(() => {
                    alertDiv.classList.remove('show');
                    setTimeout(() => alertDiv.remove(), 150);
                }, 5000);
                
                // Don't call loadAllData() to avoid resetting buttons
                console.log('Strategy started successfully');
            } else {
                // Reset button if failed
                startBtn.innerHTML = '<i class="bi bi-play-fill"></i> Start Strategy';
                startBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error starting strategy:', error);
            // Reset button on error
            startBtn.innerHTML = '<i class="bi bi-play-fill"></i> Start Strategy';
            startBtn.disabled = false;
        });
    });
    
    // Stop button click handler
    document.getElementById('stopBtn').addEventListener('click', function() {
        // Immediately disable button to prevent double clicks
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Stopping...';
        
        fetch('/api/strategy/stop', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Update status
                isRunning = false;
                
                // Update UI
                const statusBadge = document.getElementById('strategyStatus');
                statusBadge.className = 'status-badge status-stopped';
                statusBadge.innerHTML = '<i class="bi bi-circle-fill"></i> Stopped';
                
                // Update buttons
                stopBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Strategy';
                startBtn.disabled = false;
                stopBtn.disabled = true;
                
                // Show alert
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-warning alert-dismissible fade show mt-3';
                alertDiv.innerHTML = `
                    <i class="bi bi-exclamation-triangle-fill"></i> 
                    Strategy stopped successfully
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Insert alert before the form
                const card = document.querySelector('.card');
                card.parentNode.insertBefore(alertDiv, card.nextSibling);
                
                // Auto dismiss after 5 seconds
                setTimeout(() => {
                    alertDiv.classList.remove('show');
                    setTimeout(() => alertDiv.remove(), 150);
                }, 5000);
                
                // Don't call loadAllData() to avoid resetting buttons
                console.log('Strategy stopped successfully');
            } else {
                // Reset button if failed
                stopBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Strategy';
                stopBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error stopping strategy:', error);
            // Reset button on error
            stopBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Strategy';
            stopBtn.disabled = false;
        });
    });
    
    // TOTP update form handlers
    document.getElementById('updateTotpBtn').addEventListener('click', function() {
        document.getElementById('totpUpdateForm').style.display = 'block';
    });
    
    document.getElementById('cancelTotpBtn').addEventListener('click', function() {
        document.getElementById('totpUpdateForm').style.display = 'none';
    });
    
    document.getElementById('saveTotpBtn').addEventListener('click', function() {
        const secondAuthType = document.getElementById('dashboardSecondAuthType').value;
        const secondAuth = document.getElementById('dashboardSecondAuth').value;
        
        fetch('/api/auth/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                second_auth_type: secondAuthType,
                second_auth: secondAuth
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Hide form
                document.getElementById('totpUpdateForm').style.display = 'none';
                
                // Show alert
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
                alertDiv.innerHTML = `
                    <i class="bi bi-check-circle-fill"></i> 
                    Authentication updated successfully
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Insert alert before the form
                const card = document.querySelector('.card');
                card.parentNode.insertBefore(alertDiv, card.nextSibling);
                
                // Auto dismiss after 5 seconds
                setTimeout(() => {
                    alertDiv.classList.remove('show');
                    setTimeout(() => alertDiv.remove(), 150);
                }, 5000);
            }
        })
        .catch(error => console.error('Error updating authentication:', error));
    });
    
    // Export logs button click handler
    document.getElementById('exportLogsBtn').addEventListener('click', function() {
        fetch('/api/logs/export')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Create download links
                    const signalsLink = document.createElement('a');
                    signalsLink.href = data.signals_file;
                    signalsLink.download = data.signals_file.split('/').pop();
                    signalsLink.textContent = 'Download Signals CSV';
                    signalsLink.className = 'btn btn-sm btn-primary me-2';
                    
                    const positionsLink = document.createElement('a');
                    positionsLink.href = data.positions_file;
                    positionsLink.download = data.positions_file.split('/').pop();
                    positionsLink.textContent = 'Download Positions CSV';
                    positionsLink.className = 'btn btn-sm btn-primary';
                    
                    // Show alert with download links
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-success alert-dismissible fade show mt-3';
                    alertDiv.innerHTML = `
                        <i class="bi bi-check-circle-fill"></i> 
                        Logs exported successfully
                        <div class="mt-2">
                            <strong>Download:</strong>
                        </div>
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    
                    // Add download links to alert
                    const downloadDiv = alertDiv.querySelector('.mt-2');
                    downloadDiv.appendChild(signalsLink);
                    downloadDiv.appendChild(positionsLink);
                    
                    // Insert alert before the form
                    const card = document.querySelector('.card');
                    card.parentNode.insertBefore(alertDiv, card.nextSibling);
                    
                    // Auto dismiss after 15 seconds
                    setTimeout(() => {
                        alertDiv.classList.remove('show');
                        setTimeout(() => alertDiv.remove(), 150);
                    }, 15000);
                    
                    // Trigger downloads
                    setTimeout(() => {
                        window.open(data.signals_file, '_blank');
                        setTimeout(() => {
                            window.open(data.positions_file, '_blank');
                        }, 500);
                    }, 1000);
                }
            })
            .catch(error => console.error('Error exporting logs:', error));
    });
    
    // Emergency Square Off button click handler
    document.getElementById('emergencySquareOffBtn').addEventListener('click', function() {
        console.log('Emergency Square Off button clicked!');
        
        // Show confirmation dialog
        if (confirm('⚠️ EMERGENCY SQUARE OFF\n\nThis will immediately close ALL open positions!\n\nAre you sure you want to continue?')) {
            console.log('User confirmed emergency square off');
            
            fetch('/api/emergency_square_off', {
                method: 'POST'
            })
            .then(response => {
                console.log('Emergency API response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Emergency API response data:', data);
                
                if (data.status === 'success') {
                    // Show success alert
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-warning alert-dismissible fade show mt-3';
                    alertDiv.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill"></i> 
                        <strong>Emergency Square Off Completed!</strong><br>
                        <strong>Positions Closed:</strong> ${data.positions_closed}<br>
                        <strong>Total P&L:</strong> ₹${data.total_pnl}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    
                    // Insert alert before the form
                    const card = document.querySelector('.card');
                    card.parentNode.insertBefore(alertDiv, card.nextSibling);
                    
                    // Auto dismiss after 10 seconds
                    setTimeout(() => {
                        alertDiv.classList.remove('show');
                        setTimeout(() => alertDiv.remove(), 150);
                    }, 10000);
                    
                    // Refresh data
                    loadAllData();
                } else if (data.status === 'info') {
                    // Show info alert for no positions
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-info alert-dismissible fade show mt-3';
                    alertDiv.innerHTML = `
                        <i class="bi bi-info-circle-fill"></i> 
                        ${data.message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    
                    // Insert alert before the form
                    const card = document.querySelector('.card');
                    card.parentNode.insertBefore(alertDiv, card.nextSibling);
                    
                    // Auto dismiss after 5 seconds
                    setTimeout(() => {
                        alertDiv.classList.remove('show');
                        setTimeout(() => alertDiv.remove(), 150);
                    }, 5000);
                } else {
                    // Show error alert
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-3';
                    alertDiv.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill"></i> 
                        Emergency Square Off Failed: ${data.message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    
                    // Insert alert before the form
                    const card = document.querySelector('.card');
                    card.parentNode.insertBefore(alertDiv, card.nextSibling);
                    
                    // Auto dismiss after 8 seconds
                    setTimeout(() => {
                        alertDiv.classList.remove('show');
                        setTimeout(() => alertDiv.remove(), 150);
                    }, 8000);
                }
            })
            .catch(error => {
                console.error('Emergency Square Off Error:', error);
                
                // Show error alert
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-danger alert-dismissible fade show mt-3';
                alertDiv.innerHTML = `
                    <i class="bi bi-exclamation-triangle-fill"></i> 
                    Emergency Square Off Failed: Network error
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                
                // Insert alert before the form
                const card = document.querySelector('.card');
                card.parentNode.insertBefore(alertDiv, card.nextSibling);
                
                // Auto dismiss after 8 seconds
                setTimeout(() => {
                    alertDiv.classList.remove('show');
                    setTimeout(() => alertDiv.remove(), 150);
                }, 8000);
            });
        } else {
            console.log('User cancelled emergency square off');
        }
    });
});
