// This example shows how to make a decentralized price feed using multiple APIs

// Arguments can be provided when a request is initated on-chain and used in the request source code as shown below
const startDate = Number(args[0]) //timestamp seconds
const endDate = Number(args[1]) //timestamp seconds
const coordMultiplier = Number(args[4])
const precMultiplier = Number(args[5])
var lat = Number(args[2]) / coordMultiplier;
var lng = Number(args[3]) / coordMultiplier;

if (secrets.apiKey == "") {
  throw Error("METEOBLUE_API_KEY environment variable not set")
}

console.log(lat, lng, startDate, endDate, coordMultiplier, precMultiplier);

// convert timestamp to date in format yyyy-mm-dd
const startDateFormatted = new Date(startDate * 1000).toISOString().slice(0, 10);
const endDateFormattted = new Date(endDate * 1000).toISOString().slice(0, 10);

const response = await historybasic(lat, lng, startDateFormatted, endDateFormattted, secrets.apiKey);

if (!response.error) {
    const prec = response.precAvg * precMultiplier;
    const precDays = response.precDays;
    console.log(`prec: ${prec}`);
    console.log(`precDays: ${precDays}`);
    return Buffer.concat([Functions.encodeUint256(prec), Functions.encodeUint256(precDays)])
} else {
    throw Error(response.error_message);
}

async function historybasic(lat, lng, startDate, endDate, apiKey) {

    const response = await Functions.makeHttpRequest({
        url: `https://my.meteoblue.com/packages/historybasic-1h?lat=${lat}&lon=${lng}&startdate=${startDate}&enddate=${endDate}&format=json&apikey=${apiKey}`,
    })

    if (!response.error_message) {
        const chunkSize = 24; // 24 hours in a day
        const precipitationArray = response.data.history_1h.precipitation;
        const days = precipitationArray.length / chunkSize;

        // Daily average precipitation
        const precipitationSum = precipitationArray.reduce((a, b) => a + b, 0);
        const precAvg = precipitationSum / days;
        console.log(`precAvg: ${precAvg}`);
        
        // Number of rainy days
        const precipitationArrayChunks = [];
        for (let i = 0; i < precipitationArray.length; i += chunkSize) {
            const chunk = precipitationArray.slice(i, i + chunkSize);
            precipitationArrayChunks.push(chunk);
        }
        let precDays = 0;
        precipitationArrayChunks.forEach(day => {
            const dailyRain = day.reduce((a, b) => a + b, 0);
            if (dailyRain > 0) {
                precDays++;
            }
        });
        console.log(`precDays: ${precDays}`);

        // Probability of precipitation
        const precProbability = precDays / days;
        console.log(`precProbability: ${precProbability}`);

        return {precAvg, precDays, precProbability, error: false};
    } else {
        return {precAvg: 0, precDays: 0, precProbability: 0, error: true, error_message: data["error_message"]};
    }

};
