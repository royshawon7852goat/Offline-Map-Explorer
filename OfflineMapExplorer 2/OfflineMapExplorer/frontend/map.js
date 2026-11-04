/**
 * OfflineMap Explorer - Leaflet Map Canvas & QWebChannel Bridge
 */

let map = null;
let currentLayer = null;
let tileLayers = {};
let mapBridge = null;

// Route Layers
let primaryRouteLayer = null;
let altRouteLayer = null;
let routeMarkersLayer = L.layerGroup();
let searchPinMarker = null;
let gpsMarker = null;
let regionsLayer = L.layerGroup();
let bboxDrawLayer = null;

// Bounding Box Selection State
let isBboxMode = false;
let bboxStartLatLng = null;
let bboxRect = null;

// Initialize Leaflet Map
function initMap() {
  map = L.map('map', {
    center: [51.5074, -0.1278], // London center default
    zoom: 13,
    zoomControl: true,
    minZoom: 2,
    maxZoom: 18,
    preferCanvas: true
  });

  // Scale bar
  L.control.scale({ imperial: false, metric: true, position: 'bottomleft' }).addTo(map);

  // Detect runtime environment:
  // - True if inside PySide6 QtWebEngine desktop application
  // - False if opened via browser / VS Code Live Server (port 5500, etc.)
  const isQtEnv = (typeof qt !== 'undefined' && typeof qt.webChannelTransport !== 'undefined');

  function getTileUrl(layerName) {
    if (isQtEnv) {
      // Local SQLite caching & offline proxy inside Python Qt app
      return `/tiles/{z}/{x}/{y}.png?layer=${layerName}`;
    }
    // Standalone browser / VS Code Live Server fallback
    switch (layerName) {
      case 'carto_dark':
        return 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
      case 'carto_light':
        return 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png';
      case 'offline_only':
        return 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      case 'standard':
      default:
        return 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    }
  }

  function createResilientTileLayer(layerName, attribution) {
    const layer = L.tileLayer(getTileUrl(layerName), {
      maxZoom: 18,
      attribution: attribution
    });
    // Fallback if local relative tile path 404s in external web servers
    layer.on('tileerror', function (error, tile) {
      if (tile && !tile.src.startsWith('https://')) {
        tile.src = `https://tile.openstreetmap.org/${error.coords.z}/${error.coords.x}/${error.coords.y}.png`;
      }
    });
    return layer;
  }

  // Layers setup
  tileLayers = {
    standard: createResilientTileLayer('standard', '&copy; OpenStreetMap contributors'),
    carto_light: createResilientTileLayer('carto_light', '&copy; CARTO &copy; OpenStreetMap'),
    carto_dark: createResilientTileLayer('carto_dark', '&copy; CARTO &copy; OpenStreetMap'),
    offline_only: createResilientTileLayer('offline_only', 'Offline Map Storage')
  };

  currentLayer = tileLayers.standard;
  currentLayer.addTo(map);

  routeMarkersLayer.addTo(map);
  regionsLayer.addTo(map);

  // Event Listeners
  map.on('click', handleMapClick);
  map.on('moveend', handleMapMoveEnd);
  map.on('mousedown', handleMouseDown);
  map.on('mousemove', handleMouseMove);
  map.on('mouseup', handleMouseUp);

  setupUI();
  initWebChannel();
}

// Connect to Python via QWebChannel (or MockBridge for VS Code Live Server)
function initWebChannel() {
  if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined' && qt.webChannelTransport) {
    try {
      new QWebChannel(qt.webChannelTransport, function (channel) {
        mapBridge = channel.objects.mapBridge;
        window.mapBridge = mapBridge;
        console.log('QWebChannel connected successfully to Python backend.');

        // Notify Python that map canvas is ready
        if (mapBridge && mapBridge.onMapReady) {
          mapBridge.onMapReady();
        }
      });
    } catch (e) {
      console.warn('Could not initialize QWebChannel:', e);
      setupMockBridge();
    }
  } else {
    console.log('Running in browser / VS Code Live Server preview mode (standalone).');
    setupMockBridge();
  }
}

// Mock bridge for running in browser outside PySide6
function setupMockBridge() {
  window.mapBridge = {
    onMapReady: () => console.log('[MockBridge] Map ready'),
    onMapClicked: (lat, lng) => console.log('[MockBridge] Map clicked at:', lat, lng),
    onRegionSelected: (minLat, minLng, maxLat, maxLng) => {
      console.log('[MockBridge] Region selected:', minLat, minLng, maxLat, maxLng);
      alert(`Selected Bounding Box:\nMin: ${minLat.toFixed(4)}, ${minLng.toFixed(4)}\nMax: ${maxLat.toFixed(4)}, ${maxLng.toFixed(4)}\n\n(Tip: Run "python main.py" in terminal to launch the full desktop app with offline downloading & routing!)`);
    },
    setNavigationPoint: (type, lat, lng, name) => {
      console.log('[MockBridge] Navigation point set:', type, lat, lng, name);
    },
    saveBookmarkFromMap: (lat, lng, name) => {
      console.log('[MockBridge] Bookmark saved:', lat, lng, name);
    },
    onRequestCurrentLocation: () => {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            window.flyTo(pos.coords.latitude, pos.coords.longitude, 15);
            window.updateGpsPosition(pos.coords.latitude, pos.coords.longitude);
          },
          () => {
            window.flyTo(51.5074, -0.1278, 14);
            window.updateGpsPosition(51.5074, -0.1278);
          }
        );
      } else {
        window.flyTo(51.5074, -0.1278, 14);
        window.updateGpsPosition(51.5074, -0.1278);
      }
    },
    onLayerChanged: (layerId) => console.log('[MockBridge] Layer changed:', layerId),
    onMapMoved: (lat, lng, zoom) => {}
  };
  mapBridge = window.mapBridge;
}

// UI Controls Setup
function setupUI() {
  const btnLayer = document.getElementById('btn-layer-toggle');
  const layerMenu = document.getElementById('layer-menu');
  const btnBbox = document.getElementById('btn-bbox-mode');
  const btnCancelBbox = document.getElementById('btn-cancel-bbox');
  const btnGps = document.getElementById('btn-gps');
  const btnCompass = document.getElementById('btn-compass');

  btnLayer.addEventListener('click', (e) => {
    e.stopPropagation();
    layerMenu.classList.toggle('hidden');
  });

  document.addEventListener('click', () => {
    layerMenu.classList.add('hidden');
  });

  document.querySelectorAll('.layer-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      const layerId = item.getAttribute('data-layer');
      setTileLayer(layerId);
      layerMenu.classList.add('hidden');
    });
  });

  btnBbox.addEventListener('click', () => {
    toggleBboxMode(true);
  });

  btnCancelBbox.addEventListener('click', () => {
    toggleBboxMode(false);
  });

  btnGps.addEventListener('click', () => {
    if (mapBridge && mapBridge.onRequestCurrentLocation) {
      mapBridge.onRequestCurrentLocation();
    }
  });

  btnCompass.addEventListener('click', () => {
    map.setView(map.getCenter(), map.getZoom(), { animate: true });
  });
}

function setTileLayer(layerId) {
  if (!tileLayers[layerId]) return;
  map.removeLayer(currentLayer);
  currentLayer = tileLayers[layerId];
  currentLayer.addTo(map);

  document.querySelectorAll('.layer-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-layer') === layerId);
  });

  if (mapBridge && mapBridge.onLayerChanged) {
    mapBridge.onLayerChanged(layerId);
  }
}

// Map Event Handlers
function handleMapClick(e) {
  if (isBboxMode) return;
  const lat = e.latlng.lat;
  const lng = e.latlng.lng;

  // Show interactive quick action popup
  const content = document.createElement('div');
  content.innerHTML = `
    <div class="popup-title">Location (${lat.toFixed(4)}, ${lng.toFixed(4)})</div>
    <div class="popup-subtitle">Selected Map Point</div>
    <div class="popup-actions">
      <button class="popup-btn" id="pop-btn-from">Directions From</button>
      <button class="popup-btn" id="pop-btn-to">Directions To</button>
      <button class="popup-btn" id="pop-btn-fav">Bookmark</button>
    </div>
  `;

  L.popup()
    .setLatLng(e.latlng)
    .setContent(content)
    .openOn(map);

  // Hook popup buttons
  setTimeout(() => {
    const btnFrom = document.getElementById('pop-btn-from');
    const btnTo = document.getElementById('pop-btn-to');
    const btnFav = document.getElementById('pop-btn-fav');

    if (btnFrom) {
      btnFrom.onclick = () => {
        if (mapBridge && mapBridge.setNavigationPoint) {
          mapBridge.setNavigationPoint('start', lat, lng, `Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
        }
        map.closePopup();
      };
    }
    if (btnTo) {
      btnTo.onclick = () => {
        if (mapBridge && mapBridge.setNavigationPoint) {
          mapBridge.setNavigationPoint('dest', lat, lng, `Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
        }
        map.closePopup();
      };
    }
    if (btnFav) {
      btnFav.onclick = () => {
        if (mapBridge && mapBridge.saveBookmarkFromMap) {
          mapBridge.saveBookmarkFromMap(lat, lng, `Place (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
        }
        map.closePopup();
      };
    }
  }, 50);

  if (mapBridge && mapBridge.onMapClicked) {
    mapBridge.onMapClicked(lat, lng);
  }
}

function handleMapMoveEnd() {
  const center = map.getCenter();
  if (mapBridge && mapBridge.onMapMoved) {
    mapBridge.onMapMoved(center.lat, center.lng, map.getZoom());
  }
}

// Bounding Box Drag Selection
function toggleBboxMode(enable) {
  isBboxMode = enable;
  const banner = document.getElementById('bbox-banner');
  if (enable) {
    banner.classList.remove('hidden');
    map.dragging.disable();
    document.getElementById('map').style.cursor = 'crosshair';
  } else {
    banner.classList.add('hidden');
    map.dragging.enable();
    document.getElementById('map').style.cursor = '';
    if (bboxRect) {
      map.removeLayer(bboxRect);
      bboxRect = null;
    }
    bboxStartLatLng = null;
  }
}

function handleMouseDown(e) {
  if (!isBboxMode) return;
  bboxStartLatLng = e.latlng;
  if (bboxRect) {
    map.removeLayer(bboxRect);
    bboxRect = null;
  }
}

function handleMouseMove(e) {
  if (!isBboxMode || !bboxStartLatLng) return;
  const bounds = L.latLngBounds(bboxStartLatLng, e.latlng);
  if (!bboxRect) {
    bboxRect = L.rectangle(bounds, {
      color: '#2563eb',
      weight: 2,
      dashArray: '5, 5',
      fillColor: '#3b82f6',
      fillOpacity: 0.2
    }).addTo(map);
  } else {
    bboxRect.setBounds(bounds);
  }
}

function handleMouseUp(e) {
  if (!isBboxMode || !bboxStartLatLng) return;
  const bounds = L.latLngBounds(bboxStartLatLng, e.latlng);
  bboxStartLatLng = null;
  toggleBboxMode(false);

  const minLat = Math.min(bounds.getSouth(), bounds.getNorth());
  const maxLat = Math.max(bounds.getSouth(), bounds.getNorth());
  const minLng = Math.min(bounds.getWest(), bounds.getEast());
  const maxLng = Math.max(bounds.getWest(), bounds.getEast());

  // Prevent zero-size box
  if (Math.abs(maxLat - minLat) < 0.001 || Math.abs(maxLng - minLng) < 0.001) {
    return;
  }

  // Draw temporary selection
  if (bboxDrawLayer) map.removeLayer(bboxDrawLayer);
  bboxDrawLayer = L.rectangle([[minLat, minLng], [maxLat, maxLng]], {
    color: '#10b981',
    weight: 2,
    fillOpacity: 0.15
  }).addTo(map);

  if (mapBridge && mapBridge.onRegionSelected) {
    mapBridge.onRegionSelected(minLat, minLng, maxLat, maxLng);
  }
}

// ==========================================
// API Methods invoked from Python Backend
// ==========================================

window.setTheme = function (isDark) {
  if (isDark) {
    document.body.classList.remove('theme-light');
    document.body.classList.add('theme-dark');
  } else {
    document.body.classList.remove('theme-dark');
    document.body.classList.add('theme-light');
  }
};

window.setOfflineStatus = function (isOffline) {
  const badge = document.getElementById('offline-badge');
  const badgeText = document.getElementById('offline-badge-text');
  if (isOffline) {
    badge.className = 'badge-pill offline';
    badgeText.textContent = 'Offline Mode';
  } else {
    badge.className = 'badge-pill online';
    badgeText.textContent = 'Connected';
  }
};

window.flyTo = function (lat, lng, zoom) {
  map.flyTo([lat, lng], zoom || 15, { duration: 1.2 });
};

window.fitBounds = function (minLat, minLng, maxLat, maxLng) {
  map.fitBounds([[minLat, minLng], [maxLat, maxLng]], { padding: [40, 40] });
};

window.showLocationPin = function (lat, lng, title, subtitle) {
  if (searchPinMarker) {
    map.removeLayer(searchPinMarker);
  }

  const icon = L.divIcon({
    className: 'custom-pin-marker',
    html: `
      <div style="background: #ef4444; width: 28px; height: 28px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 2px solid #ffffff;">
        <div style="width: 10px; height: 10px; background: #fff; border-radius: 50%; transform: rotate(45deg);"></div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 28]
  });

  searchPinMarker = L.marker([lat, lng], { icon: icon }).addTo(map);
  searchPinMarker.bindPopup(`
    <div class="popup-title">${title}</div>
    <div class="popup-subtitle">${subtitle || ''}</div>
    <div class="popup-actions">
      <button class="popup-btn" onclick="if(window.mapBridge) window.mapBridge.setNavigationPoint('start', ${lat}, ${lng}, '${title}')">From Here</button>
      <button class="popup-btn" onclick="if(window.mapBridge) window.mapBridge.setNavigationPoint('dest', ${lat}, ${lng}, '${title}')">To Here</button>
      <button class="popup-btn" onclick="if(window.mapBridge) window.mapBridge.saveBookmarkFromMap(${lat}, ${lng}, '${title}')">Bookmark</button>
    </div>
  `).openPopup();

  map.flyTo([lat, lng], 15);
};

window.displayRoute = function (primaryCoords, altCoords, turnSteps) {
  window.clearRoute();

  if (!primaryCoords || primaryCoords.length === 0) return;

  // Draw alternative route if available
  if (altCoords && altCoords.length > 0) {
    altRouteLayer = L.polyline(altCoords, {
      color: '#9ca3af',
      weight: 5,
      dashArray: '8, 8',
      opacity: 0.8
    }).addTo(map);
  }

  // Draw primary route with glow/outline effect
  primaryRouteLayer = L.layerGroup([
    L.polyline(primaryCoords, {
      color: '#1d4ed8',
      weight: 8,
      opacity: 0.5
    }),
    L.polyline(primaryCoords, {
      color: '#3b82f6',
      weight: 5,
      opacity: 0.95
    })
  ]).addTo(map);

  // Start & End markers
  const startPt = primaryCoords[0];
  const endPt = primaryCoords[primaryCoords.length - 1];

  const startIcon = L.divIcon({
    className: 'route-start-icon',
    html: `<div style="background: #10b981; width: 22px; height: 22px; border-radius: 50%; border: 3px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display:flex; align-items:center; justify-content:center; color:white; font-size:11px; font-weight:bold;">A</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  const endIcon = L.divIcon({
    className: 'route-end-icon',
    html: `<div style="background: #ef4444; width: 22px; height: 22px; border-radius: 50%; border: 3px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display:flex; align-items:center; justify-content:center; color:white; font-size:11px; font-weight:bold;">B</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  L.marker(startPt, { icon: startIcon }).addTo(routeMarkersLayer).bindPopup("<b>Starting Point</b>");
  L.marker(endPt, { icon: endIcon }).addTo(routeMarkersLayer).bindPopup("<b>Destination</b>");

  // Fit view to route bounds
  const bounds = L.latLngBounds(primaryCoords);
  map.fitBounds(bounds, { padding: [60, 60] });
};

window.clearRoute = function () {
  if (primaryRouteLayer) {
    map.removeLayer(primaryRouteLayer);
    primaryRouteLayer = null;
  }
  if (altRouteLayer) {
    map.removeLayer(altRouteLayer);
    altRouteLayer = null;
  }
  routeMarkersLayer.clearLayers();
};

window.updateGpsPosition = function (lat, lng, heading, accuracy) {
  if (!gpsMarker) {
    const gpsIcon = L.divIcon({
      className: 'gps-pulse-marker',
      html: `<div class="gps-radar"></div><div class="gps-dot"></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });
    gpsMarker = L.marker([lat, lng], { icon: gpsIcon, zIndexOffset: 1000 }).addTo(map);
  } else {
    gpsMarker.setLatLng([lat, lng]);
  }
};

window.highlightDownloadedRegions = function (regions) {
  regionsLayer.clearLayers();
  regions.forEach(r => {
    const rect = L.rectangle([[r.min_lat, r.min_lng], [r.max_lat, r.max_lng]], {
      color: '#10b981',
      weight: 2,
      fillColor: '#10b981',
      fillOpacity: 0.12
    });
    rect.bindPopup(`<b>${r.name}</b><br>Offline Map Downloaded<br>Size: ${r.size_mb || 0} MB`);
    regionsLayer.addLayer(rect);
  });
};

window.startRegionSelectionMode = function () {
  toggleBboxMode(true);
};

// Start map initialization on DOM ready
document.addEventListener('DOMContentLoaded', initMap);
