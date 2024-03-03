document.addEventListener('DOMContentLoaded', () => {
    fetch('points.json')
        .then(response => response.json())
        .then(points => {
            initializeMap(points);
        });
});

function initializeMap(points) {
    const map = L.map('map-container').setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    const markers = [];
    for (const point of points) {
        const marker = L.marker([point.lat, point.lon]).addTo(map);
        // marker.bindPopup(`<img src="${location.imagePath}" width="200" height="150"><br>Timestamp: ${location.timestamp}`);
        marker.bindPopup(`Timestamp: ${point.timestamp}`);
        marker.on('click', () => displayGraph([point.plot1, point.plot2]));
        markers.push(marker);
    }
}

function displayGraph(graphs) {
    for (let i = 0; i < graphs.length; i++) {
        const graphData = JSON.parse(graphs[i]);

        Plotly.newPlot('graph' + String(i + 1), graphData);
    }
    // fetch('graphs.json')
    //     .then(response => response.json())
    //     .then(graphs => {
    //         const graphData = JSON.parse(graphs[pointIndex]);
    //         Plotly.newPlot('graph-container', graphData);
    //     });
}
