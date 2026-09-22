import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'tests',timeout:90000,workers:1,retries:0,
  use:{baseURL:process.env.SITE_URL || 'http://127.0.0.1:8088',headless:true,
    launchOptions:{args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']},
    screenshot:'only-on-failure'},
  webServer:process.env.SITE_URL ? undefined : {command:'python3 -m http.server 8088 --bind 127.0.0.1 --directory dist',url:'http://127.0.0.1:8088',reuseExistingServer:false}
});
