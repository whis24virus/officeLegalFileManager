let safe = "Assassin's Creed 2 7. Assassin's Creed 3 8. Assassin's Creed 4 Black Flag * another item - yet another";
safe = safe.replace(/ (\d+\.\s)/g, '\n$1');
safe = safe.replace(/ (\*\s)/g, '\n$1');
safe = safe.replace(/ (-\s)/g, '\n$1');
console.log(safe);
