# Engenharia reversa e estudo — Sentinel Atlas

## Objetivo e fluxo

Posições, cercas virtuais e camadas de dados geográficos. O backend FastAPI separa a entrada HTTP, a consulta de camadas e a análise. Comece em backend/app.py, siga os tipos de entrada e compare com backend/geo_layers.py e o cliente web.

**Tecnologias identificadas** · JavaScript, Python, TypeScript, FastAPI, SQLite.

**Revisão de referência** · `d8366a7e74aa`.

## Mapa do código

| Caminho | Papel de leitura | Símbolos selecionados |
| --- | --- | --- |
| [backend/ai.py](../backend/ai.py) | Implementação | `GeoINTAnalyzer`, `GeoINTAnalyzer._calculate_distance_km`, `GeoINTAnalyzer.analyze_situation`, `GeoINTAnalyzer.query_copilot` |
| [backend/alerts.py](../backend/alerts.py) | Implementação | `send_webhook` |
| [backend/app.py](../backend/app.py) | Ponto de leitura para entrada ou composição | `validate_analysis_items`, `AIAnalyzeInput`, `AIAnalyzeInput.validate_assets`, `AIAnalyzeInput.validate_fences`, `AIQueryInput` |
| [backend/geo_layers.py](../backend/geo_layers.py) | Implementação | `catalog`, `_coord`, `_request`, `_point`, `_number` |
| [backend/location.py](../backend/location.py) | Implementação | `get_location_info` |
| [backend/orbits.py](../backend/orbits.py) | Implementação | `_gmst_radians`, `propagate_tle` |
| [backend/routing.py](../backend/routing.py) | Implementação | `_validate_coordinate`, `bicycle_route` |
| [backend/shared_limits.py](../backend/shared_limits.py) | Implementação | `SharedLimits`, `SharedLimits._connect`, `SharedLimits.allow_login`, `SharedLimits.acquire`, `SharedLimits.renew` |
| [backend/source_clients.py](../backend/source_clients.py) | Implementação | `SourceUnavailable`, `NoRedirect`, `NoRedirect.redirect_request`, `_fetch_bytes`, `fetch_json` |
| [backend/storage.py](../backend/storage.py) | Implementação | `_retention_limit_from_environment`, `GeofenceStore`, `GeofenceStore.create_session`, `GeofenceStore.session_valid`, `GeofenceStore.revoke_session` |
| [data/adminBoundaries.js](../data/adminBoundaries.js) | Implementação | `normalizeAdminName`, `ringAreaKm2`, `haversineKm`, `decodeRing`, `pointInRing` |
| [data/adsbLolFallback.js](../data/adsbLolFallback.js) | Implementação | `finiteNumber`, `emitterCategory`, `normalizeAdsbLolAircraftState`, `normalizeAdsbLolPointResponse` |
| [data/aircraftClass.js](../data/aircraftClass.js) | Implementação | `classifyAircraft` |
| [data/aircraftEmergency.js](../data/aircraftEmergency.js) | Implementação | `normalizeSquawk`, `aircraftEmergency`, `emergencyBroadcastPhrase`, `isEmergency` |
| [data/aircraftIcons.js](../data/aircraftIcons.js) | Implementação | `aircraftIcon`, `_b64` |
| [data/aircraftMeta.js](../data/aircraftMeta.js) | Implementação | `stickyText`, `stickyNumber` |
| [data/aircraftNearbyPolicy.js](../data/aircraftNearbyPolicy.js) | Implementação | `aircraftIncludedInNearby` |
| [data/aircraftRecession.js](../data/aircraftRecession.js) | Implementação | `clamp`, `resolvedParams`, `aircraftRecessionFactorsResolved`, `setAircraftRecessionParams`, `getAircraftRecessionParams` |
| [data/aisLiveVessels.js](../data/aisLiveVessels.js) | Implementação | — |
| [data/aisStreamAdapter.js](../data/aisStreamAdapter.js) | Implementação | `parseRetryAfterMs`, `classifyAisFailure`, `decodeAisFrameSync`, `decodeAisFrame`, `aisFrameByteLength` |
| [data/aisWatchdog.js](../data/aisWatchdog.js) | Implementação | `isLiveAisStatus`, `parseSilenceTimeoutEnv`, `createAisWatchdog`, `release`, `isExhausted` |
| [data/alprCameras.js](../data/alprCameras.js) | Implementação | — |
| [data/analystEngine.js](../data/analystEngine.js) | Implementação | `analystFieldsFor`, `toEpochMs`, `haversineKm`, `applyFilter`, `applyScope` |
| [data/approxDistance.js](../data/approxDistance.js) | Implementação | `approxDistanceKm` |
| [data/bhoteKoshiEmbeddedMedia.js](../data/bhoteKoshiEmbeddedMedia.js) | Implementação | `bhoteEventText`, `loadYouTubeApi`, `createTrimmedYouTubePlayback`, `facebookSdkReady`, `loadFacebookSdk` |
| [data/bhoteKoshiEvent.js](../data/bhoteKoshiEvent.js) | Implementação | `clampUnit`, `elapsedLabel`, `visibleSegmentCount`, `updateCorridorPositionCache`, `floodProgressForStoryProgress` |
| [data/bhoteKoshiFloodPath.js](../data/bhoteKoshiFloodPath.js) | Implementação | — |
| [data/bhoteKoshiIncidentPlaces.js](../data/bhoteKoshiIncidentPlaces.js) | Implementação | — |
| [data/bhoteKoshiLocator.js](../data/bhoteKoshiLocator.js) | Implementação | `placeTitle`, `abortError`, `normalizePresentation`, `presentationUsesBoundary`, `presentationAnimatesBoundary` |
| [data/bhoteKoshiShotPaths.js](../data/bhoteKoshiShotPaths.js) | Implementação | `nearestVertex`, `buildSourceShotPaths`, `add` |
| [data/bikeshare.js](../data/bikeshare.js) | Implementação | — |
| [data/bundledJson.js](../data/bundledJson.js) | Implementação | `loadBundledJson` |
| [data/cameraArrival.js](../data/cameraArrival.js) | Implementação | `cancelCameraArrival`, `ownCameraArrival` |
| [data/cameraFraming.js](../data/cameraFraming.js) | Implementação | `rangeForBoundingSphere` |
| [data/cameraSensitivity.js](../data/cameraSensitivity.js) | Implementação | `ledgerFor`, `applyLedger`, `claimCameraSensitivity`, `releaseCameraSensitivity`, `cameraSensitivityClaims` |
| [data/cctv.js](../data/cctv.js) | Implementação | — |
| [data/cctvCards.js](../data/cctvCards.js) | Implementação | `isCctvCardAnchorSafe`, `declutterCctvCards`, `cardScaleForAltitude`, `cardFetchPolicy`, `createFrameSlot` |
| [data/cctvFootprint.js](../data/cctvFootprint.js) | Implementação | `projectPoint`, `planeDimensions`, `planeSupportPoints`, `supportAltitude`, `requiredPlaneLift` |
| [data/cctvGizmo.js](../data/cctvGizmo.js) | Implementação | `closestParamOnAxis`, `rayPlaneIntersect`, `ringAngle`, `signedAngleDelta`, `enuAxes` |
| [data/cctvLod.js](../data/cctvLod.js) | Implementação | `cctvLodBudgets`, `incumbentRankKm`, `hasFiniteCctvViewport`, `screenCenterFraction`, `cctvCandidateSpreadKm` |
| [data/cctvViewshed.js](../data/cctvViewshed.js) | Implementação | `cameraHue`, `viewshedColors`, `frustumVolumeGeometryData`, `createFrustumVolumePrimitive` |
| [data/cockpitAirLod.js](../data/cockpitAirLod.js) | Implementação | `nextCockpitNearContacts` |
| [data/cockpitContactDot.js](../data/cockpitContactDot.js) | Implementação | `cockpitContactDotImage` |
| [data/contactMatch.js](../data/contactMatch.js) | Implementação | `canonicalizeContactId`, `rankContactMatch`, `contactMatchWins` |
| [data/contactPlayback.js](../data/contactPlayback.js) | Implementação | `createLagReservoir`, `addLag`, `percentile`, `createHistoryBudget`, `createFixSample` |
| [data/contactTrailRenderer.js](../data/contactTrailRenderer.js) | Implementação | `trailAlpha`, `createContactTrailRenderer`, `geometry`, `primitive`, `tint` |
| [data/contextStore.js](../data/contextStore.js) | Implementação | `createStore`, `getContextStore`, `hasContextHost`, `registerEntityContext`, `selectEntityContext` |
| [data/dataCredits.js](../data/dataCredits.js) | Implementação | `updateOsmDisplay`, `showOsmCredit`, `hideOsmCredit`, `transitFeedCredit`, `registerDynamicCredit` |
| [data/detection.js](../data/detection.js) | Implementação | `detectionDebugRequested`, `_nowMs`, `countFadingRenderEntries`, `initDetection`, `destroyDetection` |
| [data/detectionCohort.js](../data/detectionCohort.js) | Implementação | `cohortCapForQuota`, `stableIdentityHash`, `compareCohortContenders`, `isWorse`, `BoundedCohort` |
| [data/detectionDraw.js](../data/detectionDraw.js) | Implementação | `formatFlightLevel`, `formatKnots`, `monoTextWidth`, `composeLabel`, `acquireAlpha` |
| [data/detectionPolicy.js](../data/detectionPolicy.js) | Implementação | `aircraftBracketAlphaFloor`, `detectionBracketAlpha`, `detectionHorizontalSector`, `canonicalizeDensity`, `profileForDensity` |
| [data/detectionPresentation.js](../data/detectionPresentation.js) | Implementação | `detectionBracketOpacity` |
| [data/detectionRenderDemand.js](../data/detectionRenderDemand.js) | Implementação | `scanlineOffsetPx`, `detectionNeedsFollowUpFrame`, `detectionPaintSkipDecision`, `renderEntryIsAnimating`, `countAnimatingRenderEntries` |
| [data/directionText.js](../data/directionText.js) | Implementação | `directionToHeading` |
| [data/directions.js](../data/directions.js) | Implementação | `createApplicationDirectionsLayer` |
| [data/earthquakes.js](../data/earthquakes.js) | Implementação | `createEarthquakesLayer` |
| [data/feedState.js](../data/feedState.js) | Implementação | `layerFeedState` |
| [data/fireAnchors.js](../data/fireAnchors.js) | Implementação | — |
| [data/firmsAdapt.js](../data/firmsAdapt.js) | Implementação | `adaptFirmsRecords`, `normalizeConfidence`, `parseAcquisitionMs`, `normalizeSensor`, `clamp01` |
| [data/firmsCsv.js](../data/firmsCsv.js) | Implementação | `isLikelyCsv`, `parseFirmsCsv`, `acquisitionMsUtc`, `filterTrailing24h`, `cell` |
| [data/firmsHeatmap.js](../data/firmsHeatmap.js) | Implementação | `createFirmsHeatmapLayer` |
| [data/firmsLabels.js](../data/firmsLabels.js) | Implementação | `fireDetectionKey`, `accentForSeverity`, `satelliteShortName` |
| [data/flights.js](../data/flights.js) | Implementação | — |
| [data/flowMatch.js](../data/flowMatch.js) | Implementação | `median`, `bearingDeg`, `bearingDiffDeg`, `pointSegDist2`, `createFlowSegmentIndex` |
| [data/flowTiles.js](../data/flowTiles.js) | Implementação | — |
| [data/focusDeemphasis.js](../data/focusDeemphasis.js) | Implementação | `clamp`, `resolvedParams`, `focusTargetEmphasisResolved`, `smoothFocusEmphasisResolved`, `setFocusDeemphasisParams` |
| [data/gbfsSource.js](../data/gbfsSource.js) | Implementação | `isAllowedGbfsHost`, `isAllowedGbfsPath`, `gbfsUpstreamHeaders`, `gbfsCacheControl` |
| [data/geoFileImport.js](../data/geoFileImport.js) | Implementação | `GeoImportError`, `detectGeoFileFormat`, `importDisplayName`, `parseGeoJsonText`, `countGeoJsonGeometry` |
| [data/geoImportImages.js](../data/geoImportImages.js) | Implementação | `importImageSize`, `createImportImageBudget`, `ascii`, `u24` |
| [data/geoImportPins.js](../data/geoImportPins.js) | Implementação | `ImportedBillboards`, `createImportedPins` |
| [data/geoid.js](../data/geoid.js) | Implementação | `ensureGeoidReady`, `geoidHeight`, `orthometricToEllipsoidal`, `ellipsoidalToMslDisplayM` |
| [data/groundFloor.js](../data/groundFloor.js) | Implementação | — |
| [data/groundSnap.js](../data/groundSnap.js) | Implementação | `createGroundSnap` |
| [data/gtfsRealtime.js](../data/gtfsRealtime.js) | Implementação | `readBoundedString`, `readFeedHeader`, `readTripDescriptor`, `readPosition`, `readVehicleDescriptor` |
| [data/iconOrientation.js](../data/iconOrientation.js) | Implementação | `screenProjectedRotation`, `stabilizeScreenRotation`, `skyBackdropFactor`, `horizonOccluder`, `cameraPoseSignature` |
| [data/idSwitches.js](../data/idSwitches.js) | Implementação | `normalizeIdSwitches`, `encodeIdSwitches`, `decodeIdSwitches`, `patchRequestedIdSwitches` |
| [data/infrastructure.js](../data/infrastructure.js) | Implementação | `createInfrastructureLayers` |
| [data/infrastructureOverlayEntry.js](../data/infrastructureOverlayEntry.js) | Implementação | `createInfrastructureOverlayEntry` |
| [data/inputOwnership.js](../data/inputOwnership.js) | Implementação | `claimPointer`, `releasePointer`, `pointerOwner`, `isPointerFree`, `isPointerOwnedBy` |
| [data/installationFeedback.js](../data/installationFeedback.js) | Implementação | `describeInstallationFeedback`, `installationFeedback` |
| [data/installationNames.js](../data/installationNames.js) | Implementação | — |
| [data/issPass.js](../data/issPass.js) | Implementação | `findNextIssPass` |
| [data/labelArbiter.js](../data/labelArbiter.js) | Implementação | `zeroCount`, `clampInt`, `demandEntries`, `redistributeUnused`, `allocateLayerQuotasInto` |
| [data/layerSnapshot.js](../data/layerSnapshot.js) | Implementação | `snapshotError`, `snapshotAgeSec`, `snapshotAgeLabel`, `worstFeedState`, `layerSnapshot` |
| [data/layerState.js](../data/layerState.js) | Implementação | `normalizeBoolean`, `normalizeEnum`, `normalizeRadioFilter`, `encodeRadioFilter`, `decodeRadioFilter` |
| [data/layerStateCoordinator.js](../data/layerStateCoordinator.js) | Implementação | `safeStorage`, `currentLayerOutcome`, `LayerStateCoordinator`, `settle`, `poll` |
| [data/lifecycle.js](../data/lifecycle.js) | Implementação | `cloneLayerParams`, `isAbortError`, `lifecycleRejectedError`, `paramsRejectedError`, `isExplicitLayerIntentOrigin` |
| [data/localGeojson.js](../data/localGeojson.js) | Implementação | `createLocalGeoJsonLayer`, `createLocalInfrastructureOverlayPublisher` |
| [data/localGeojsonCore.js](../data/localGeojsonCore.js) | Implementação | `localInfrastructureOverlayCopy`, `createLocalInfrastructureOverlayEntry`, `selectLocalInfrastructureOverlayCohort`, `createLocalInfrastructureOverlayPublisher`, `localDatasetError` |
| [data/localGeojsonLod.js](../data/localGeojsonLod.js) | Implementação | `infraLodBudget`, `infraRankScore`, `sortableDistance`, `selectInfraLod`, `applyInfraEvictionGrace` |
| [data/localLayers.js](../data/localLayers.js) | Implementação | — |
| [data/manager.js](../data/manager.js) | Implementação | `DataLayerManager` |
| [data/meshFloorSampler.js](../data/meshFloorSampler.js) | Implementação | — |
| [data/militaryAwareness.js](../data/militaryAwareness.js) | Implementação | — |
| [data/militaryAwarenessEngine.js](../data/militaryAwarenessEngine.js) | Implementação | `findByDoublingRadius`, `formatAwarenessDistance`, `formatAwarenessLabel`, `summarizeAwarenessCohort`, `getAwarenessNavigationTargets` |
| [data/militaryFlights.js](../data/militaryFlights.js) | Implementação | — |
| [data/militaryInstallationData.js](../data/militaryInstallationData.js) | Implementação | `humanizeInstallationClass`, `finiteLatitude`, `finiteLongitude`, `pointFrom`, `footprintFrom` |
| [data/militaryInstallations.js](../data/militaryInstallations.js) | Implementação | — |
| [data/militaryNames.js](../data/militaryNames.js) | Implementação | `createMilitaryNamesLoader`, `nameMilitaryFragment`, `militaryNamesInView` |
| [data/militaryRegistry.js](../data/militaryRegistry.js) | Implementação | — |
| [data/modelEligibility.js](../data/modelEligibility.js) | Implementação | `selectModelEligible` |
| [data/modelVisualAnchor.js](../data/modelVisualAnchor.js) | Implementação | `modelAnchorWorld`, `visualCenterForModel`, `trailAnchorForModel`, `trailHeadStart`, `modelVisualAnchor` |
| [data/motionModel.js](../data/motionModel.js) | Implementação | `norm360`, `liftRepeatedGroundFix`, `norm180`, `courseBetweenCartesians`, `speedRamp` |
| [data/naturalEarthRegions.js](../data/naturalEarthRegions.js) | Implementação | `ringAreaKm2`, `normalizeName`, `suffixVariants`, `buildEntries`, `toResult` |
| [data/neighborhoodPolygons.js](../data/neighborhoodPolygons.js) | Implementação | `normalize`, `pointInRing`, `toPolygons`, `containingOuterRing`, `largestOuterRing` |
| [data/pickRegistry.js](../data/pickRegistry.js) | Implementação | `resolvePickId`, `registerPickOwner`, `unregisterPickOwner`, `findPickOwner`, `isOwnedByOtherLayer` |
| [data/pickedContext.js](../data/pickedContext.js) | Implementação | `text`, `finite`, `pickedKindForLayer`, `contextCarrierRecord`, `fromRecord` |
| [data/placeProviderPayloads.js](../data/placeProviderPayloads.js) | Implementação | `placeContextPriority`, `approximateDistanceM`, `projectNearbyPlaces`, `projectTextSearchPlaces`, `normalizeRouteProfile` |
| [data/pointerOwnerNames.js](../data/pointerOwnerNames.js) | Implementação | `pointerOwnerName` |
| [data/radio.js](../data/radio.js) | Implementação | — |
| [data/radioCountry.js](../data/radioCountry.js) | Implementação | `countryKey`, `canonicalCountryName`, `normalizeRadioCountryInput`, `isRadioCountryCode` |
| [data/regionalBrief.js](../data/regionalBrief.js) | Implementação | `fetchRegionalBrief` |
| [data/regionalModel.js](../data/regionalModel.js) | Implementação | `cleanText`, `safeHttpUrl`, `normalizeRegionalPlace`, `normalizeRegionalArticles`, `observedNumber` |
| [data/renderAltitude.js](../data/renderAltitude.js) | Implementação | `pickRenderAltitudeM`, `reuseGroundedSurfaceM`, `geoidSurfaceLastResortM` |
| [data/retryableLoad.js](../data/retryableLoad.js) | Implementação | `createRetryableLoader`, `attempt` |
| [data/rocketLaunches.js](../data/rocketLaunches.js) | Implementação | — |
| [data/routePlausible.js](../data/routePlausible.js) | Implementação | `bearingRad`, `crossTrackKm`, `alongTrackKm`, `routePlausible`, `near` |
| [data/routeSteps.js](../data/routeSteps.js) | Implementação | `cleanText`, `roadLabel`, `ontoRoad`, `direction`, `ordinal` |
| [data/satelliteClass.js](../data/satelliteClass.js) | Implementação | `satelliteClassOf`, `satelliteClassColor`, `satelliteClassLabel`, `tallySatelliteClasses`, `satelliteClassLegend` |
| [data/satellitePass.js](../data/satellitePass.js) | Implementação | `lookAnglesAt`, `solarPositionECI`, `isSatelliteSunlit`, `observerSolarElevation`, `isObserverDark` |
| [data/satellites.js](../data/satellites.js) | Implementação | — |
| [data/scenePick.js](../data/scenePick.js) | Implementação | `isPickedWorldPosition`, `pickGroundPosition`, `isSurfacePick` |
| [data/spaceProviderRequests.js](../data/spaceProviderRequests.js) | Implementação | `celestrakTleUrl`, `launchLibraryRecentUrl` |
| [data/spriteOrder.js](../data/spriteOrder.js) | Implementação | `registerSpriteCollection`, `unregisterSpriteCollection`, `restoreSpriteOrder`, `restoreSpriteOrderOnEnable` |
| [data/surfaceServices.js](../data/surfaceServices.js) | Implementação | — |
| [data/tapAddress.js](../data/tapAddress.js) | Implementação | `isLocalIpv4`, `parseTapAddress`, `tapUrl` |
| [data/telegeographySubmarineCables.js](../data/telegeographySubmarineCables.js) | Implementação | `createTeleGeographySubmarineCableLayer`, `createCableOverlayPublisher` |
| [data/terrainHeights.js](../data/terrainHeights.js) | Implementação | — |
| [data/terrainHeightsProxy.js](../data/terrainHeightsProxy.js) | Implementação | `defaultSleep`, `parseTerrainPoints`, `terrainPointKey`, `canonicalTerrainPoint`, `validTerrainResult` |
| [data/tomtomTiles.js](../data/tomtomTiles.js) | Implementação | `isValidTileCoord`, `lonLatToTile`, `tileToBBox`, `tilesForBounds`, `utcDayKey` |
| [data/tr3bRegistry.js](../data/tr3bRegistry.js) | Implementação | `key`, `isTr3b`, `setTr3b`, `toggleTr3b`, `tr3bConvertedIds` |
| [data/trackedCamera.js](../data/trackedCamera.js) | Implementação | `trackedModelScaleForPixelCap`, `trackedDisplayPositionForCamera`, `acquireStableTrackedZoom`, `clampTrackedCameraPosition`, `applyTrackedCameraFrame` |
| [data/trackedModelRegime.js](../data/trackedModelRegime.js) | Implementação | `trackedModelZoomActive` |
| [data/trackedReadout.js](../data/trackedReadout.js) | Implementação | `trackedLabelModelFromText`, `cachedTrackedDisplayPosition`, `cachedTrackedVisualPosition`, `entryIdFor`, `activeEntity` |
| [data/trackingClickGesture.js](../data/trackingClickGesture.js) | Implementação | `isTrackingSelectionGesture`, `isTrackingClickGesture`, `bindTrackingClickGesture`, `appendTravel`, `finishPress` |
| [data/traffic.js](../data/traffic.js) | Implementação | — |
| [data/trafficBounds.js](../data/trafficBounds.js) | Implementação | `initialBearingRad`, `destinationPoint`, `deriveFetchCenter`, `longitudeSpanDeg`, `boundedLongitudeRange` |
| [data/trafficFlowStyle.js](../data/trafficFlowStyle.js) | Implementação | `flowBucket`, `flowColor`, `flowSpeedScale`, `flowDensityMult` |
| [data/trafficPresetStyle.js](../data/trafficPresetStyle.js) | Implementação | `trafficStyleProfile`, `presetDotRgba`, `presetSizeDelta`, `presetDotOutline`, `trafficBucketTier` |
| [data/trafficQueue.js](../data/trafficQueue.js) | Implementação | `queuePlatoons`, `queueDistances`, `locateAlongRoad` |
| [data/trailRenderer.js](../data/trailRenderer.js) | Implementação | `createTrail`, `ensureEntity` |
| [data/transit.js](../data/transit.js) | Implementação | — |
| [data/transitFeeds.js](../data/transitFeeds.js) | Implementação | `mbtaRouteMode`, `enturRouteMode`, `hslRouteMode`, `metroTransitRouteMode`, `ttcRouteMode` |
| [data/transitIcons.js](../data/transitIcons.js) | Implementação | `haloFrame`, `transitIconCacheSize`, `transitIcon`, `_b64` |
| [data/transitPresetStyle.js](../data/transitPresetStyle.js) | Implementação | `transitStyleProfile`, `presetSpriteRgba`, `presetSpriteScale`, `presetSpriteOutlinePx`, `transitModeTier` |
| [data/transitProxy.js](../data/transitProxy.js) | Implementação | `isTransitRedirectStatus`, `resolveTransitRoute`, `transitUpstreamHeaders`, `isAcceptableTransitUpstreamUrl`, `transitRedirectDecision` |
| [data/vesselLabels.js](../data/vesselLabels.js) | Implementação | `displayVesselType`, `vesselTypeCss`, `accentForVesselType`, `styleForType`, `vesselOverlayCohortLimit` |
| [data/vesselTypes.js](../data/vesselTypes.js) | Implementação | `normalizeVesselType` |
| [data/wind.js](../data/wind.js) | Implementação | `createWindLayer` |
| [python/gps_core.py](../python/gps_core.py) | Implementação | `Position`, `Geofence`, `distance_meters`, `parse_nmea_rmc`, `AutomationEngine` |
| [python/settings.py](../python/settings.py) | Implementação | `_load_local_env`, `_optional_env`, `Settings`, `Settings.from_environment`, `Settings.enabled_sources` |
| [typescript/gps_client.ts](../typescript/gps_client.ts) | Implementação | `sendGpsEvent` |
| [web/service-worker.js](../web/service-worker.js) | Implementação | — |
| [web/index.html](../web/index.html) | Marcação ou estilos da interface | `setFocusMode`, `estimateSubsolarPoint`, `initializeSentinel`, `buildRingsData`, `updateOverview` |

## Configuração e referências

A [arquitetura](ARQUITETURA.md) detalha as responsabilidades e os vínculos do sistema.

Ambiente e dependências: [Dockerfile](../Dockerfile), [backend/requirements.txt](../backend/requirements.txt), [compose.yaml](../compose.yaml), [docker-compose.yml](../docker-compose.yml).

Referências existentes: [DATA_SOURCES.md](../DATA_SOURCES.md), [data/fixtures/README.md](../data/fixtures/README.md), [data/local_data/cctv_ground_heights/README.md](../data/local_data/cctv_ground_heights/README.md), [data/local_data/dams/README.md](../data/local_data/dams/README.md), [data/local_data/datacenters/README.md](../data/local_data/datacenters/README.md), [data/local_data/natural_earth/README.md](../data/local_data/natural_earth/README.md), [data/local_data/neighborhoods/SOURCE.md](../data/local_data/neighborhoods/SOURCE.md), [data/local_data/osm_military_names/README.md](../data/local_data/osm_military_names/README.md), [data/local_data/sky/README.md](../data/local_data/sky/README.md), [data/local_data/telegeography_submarine_cables/README.md](../data/local_data/telegeography_submarine_cables/README.md).

## Roteiro de estudo e desenvolvimento

1. Comece pelo fluxo descrito acima e localize seus pontos de entrada no mapa. Acompanhe uma entrada válida até a transformação ou a resposta.
2. Abra um teste relacionado ao fluxo e descreva qual regra ele protege. Compare o tratamento esperado para entradas válidas, inválidas e nos limites.
3. Ao adicionar uma regra, determine qual módulo controla o dado e cubra o caso nesse nível. Em seguida, confira o efeito no comando, na API ou na interface de entrada.

**Pergunta de entrevista**

Como impedir que a indisponibilidade de uma fonte geográfica comprometa todas as camadas?

## Testes versionados

Arquivos para começar a leitura dos cenários de teste: [data/adminBoundaries.test.mjs](../data/adminBoundaries.test.mjs), [data/adsbLolFallback.test.mjs](../data/adsbLolFallback.test.mjs), [data/aircraftClass.test.mjs](../data/aircraftClass.test.mjs), [data/aircraftEmergency.test.mjs](../data/aircraftEmergency.test.mjs), [data/aircraftEmergencyAnalyst.test.mjs](../data/aircraftEmergencyAnalyst.test.mjs), [data/aircraftMeta.test.mjs](../data/aircraftMeta.test.mjs), [data/aircraftNearbyPolicy.test.mjs](../data/aircraftNearbyPolicy.test.mjs).

Os comandos e versões de runtime usados no CI ficam em [.github/workflows/ci.yml](../.github/workflows/ci.yml).

[Voltar ao README](../README.md).
