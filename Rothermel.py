import math
def GetSimpleFireSpread(fuelload, fueldepth, windspeed, slope, fuelmoisture, fuelsav):
    # Parameters
    maxval= 0
    if fuelload > 0:
        wo = fuelload # Ovendry fuel loading in (lb/ft^2). Amount of primary prod???
        fd = fueldepth # Fuel depth (ft)
        wv = windspeed * 88# Wind velocity at midflame height (ft/minute) = 88 * mph
        fpsa = fuelsav  # Fuel Particle surface area to volume ratio (1/ft)
        mf = fuelmoisture  # Fuel particle moisture content
        h = 8000  # Fuel particle low heat content
        pp = 32.  # Ovendry particle density
        st = 0.0555  # Fuel particle mineral content
        se = 0.010  # Fuel Particle effective mineral content
        mois_ext = 0.12  # Moisture content of extinction or 0.3 if dead
        #calculate slope as degrees
        slope_rad = math.atan(slope)
        slope_degrees = slope_rad / 0.0174533 #radians
        tan_slope = math.tan(slope_rad) #  in radians
        # Betas Packing ratio
        Beta_op = 3.348 * math.pow(fpsa, -0.8189)  # Optimum packing ratio
        ODBD = wo / fd  # Ovendry bulk density
        Beta = ODBD / pp #Packing ratio
        #Beta = 0.00158
        Beta_rel = Beta / Beta_op
        # Reaction Intensity
        WN = wo / (1 + st)  # Net fuel loading
        #A = 1 / (4.774 * pow(fpsa, 0.1) - 7.27)  # Unknown const
        A =  133.0 / math.pow(fpsa, 0.7913) #updated A
        T_max = math.pow(fpsa,1.5) * math.pow(495.0 + 0.0594 * math.pow(fpsa, 1.5),-1.0)  # Maximum reaction velocity
        #T_max = (fpsa*math.sqrt(fpsa)) / (495.0 + 0.0594 * fpsa * math.sqrt(fpsa))
        T = T_max * math.pow((Beta / Beta_op),A) * math.exp(A * (1 - Beta / Beta_op))  # Optimum reaction velocity
        # moisture dampning coefficient
        NM = 1. - 2.59 * (mf / mois_ext) + 5.11 * math.pow(mf / mois_ext, 2.) - 3.52 * math.pow(mf / mois_ext,3.)  # Moisture damping coeff.
        # mineral dampning
        NS = 0.174 * math.pow(se, -0.19)  # Mineral damping coefficient
        #print(T, WN, h, NM, NS)
        RI = T * WN * h * NM * NS
        #RI = 874
        # Propogating flux ratio
        PFR = math.pow(192.0 + 0.2595 * fpsa, -1) * math.exp(
            (0.792 + 0.681 * fpsa ** 0.5) * (Beta + 0.1))  # Propogating flux ratio
        ## Wind Coefficient
        B = 0.02526 * math.pow(fpsa, 0.54)
        C = 7.47 * math.exp(-0.1333 * math.pow(fpsa, 0.55))
        E = 0.715 * math.exp(-3.59 * 10**-4 * fpsa)
        #WC = C * wv**B * math.pow(Beta / Beta_op, -E) #wind coefficient
        if wv > (0.9 * RI): #important - don't know source. Matches BEHAVE
            wv = 0.9 * RI
        WC = (C * wv ** B) * math.pow((Beta / Beta_op), (-E))
        #WC= WC*0.74
        #Slope  coefficient
        SC = 5.275*(Beta**-0.3)*tan_slope**2
        #Heat sink

        EHN = math.exp(-138. / fpsa)  # Effective Heating Number = f(surface are volume ratio)
        QIG = 250. + 1116. * mf  # Heat of preignition= f(moisture content)
        # rate of spread (ft per minute)
        #RI = BTU/ft^2
        numerator = (RI * PFR * (1 + WC + SC))
        denominator = (ODBD * EHN * QIG)
        R = numerator / denominator #WC and SC will be zero at slope = wind = 0
        RT = 384.0/fpsa
        HA = RI*RT
        #fireline intensity as described by Albini via USDA Forest Service RMRS-GTR-371. 2018
        FI = (384.0/fpsa)*RI*(R) ##Uses Reaction Intensity in BTU / ft/ min
        #FI = HA*R
        if (RI <= 0):
            return (maxval, maxval, maxval)
        return (R, RI, FI)
    else:
        return (maxval, maxval, maxval)




fuelload = 0.033976 #lbs/ft^2
fueldepth = 1 #feet
windspeed = 5 #mph
slope = 10 #degrees
fuelmoisture = 0.05# as a proportion
fuelsav = 3500#1/ft
result = GetSimpleFireSpread (fuelload, fueldepth, windspeed, slope, fuelmoisture, fuelsav)

print("Rate of spread (ft/min)", result[0])
print("Reaction Intensity (Btu/ft/min)", result[1])
print("Fireline Intensity (Btu/ft)", result[2])

