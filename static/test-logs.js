// Function to add test signals to the database
function addTestSignals() {
    // Create test signals
    const testSignals = [
        {
            token: "1",
            symbol: "RELIANCE",
            signal_type: "BUY",
            price: 2500.50,
            high_price: 2550.75,
            stop_loss: 2450.25,
            percent_change: 2.5
        },
        {
            token: "2",
            symbol: "TCS",
            signal_type: "BUY",
            price: 3450.75,
            high_price: 3500.00,
            stop_loss: 3400.50,
            percent_change: 1.8
        },
        {
            token: "3",
            symbol: "INFY",
            signal_type: "SELL",
            price: 1380.25,
            high_price: 1420.50,
            stop_loss: 1400.00,
            percent_change: -2.1
        }
    ];
    
    // Send test signals to the server
    fetch('/api/test/add_signals', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ signals: testSignals })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Test signals added successfully');
            // Refresh the logs
            window.location.reload();
        } else {
            console.error('Error adding test signals:', data.message);
        }
    })
    .catch(error => console.error('Error adding test signals:', error));
}

// Add button to the logs tab
document.addEventListener('DOMContentLoaded', function() {
    const logsHeader = document.querySelector('#pills-logs .card-header');
    
    if (logsHeader) {
        // Create test button
        const testButton = document.createElement('button');
        testButton.className = 'btn btn-sm btn-outline-primary me-2';
        testButton.innerHTML = '<i class="bi bi-plus-circle"></i> Add Test Logs';
        testButton.onclick = addTestSignals;
        
        // Add button before the export button
        const exportButton = document.getElementById('exportLogsBtn');
        logsHeader.insertBefore(testButton, exportButton);
    }
});
